package ai.rescuenet.field.codec

import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.codec.WireLimits as L

/**
 * The bit-packed SMS codec — **`09` §6.6, DM-57**.
 *
 * A **lossless bijection** over what it accepts (DM-25): `decode(encode(x)) == x`
 * for every representable batch. It **never truncates** — a value that does not
 * fit raises [WireEncodingException] and the caller leaves the event `PENDING`
 * (`08` §10.1 rule 2). It never reorders, merges, drops or synthesises events
 * (rule 3), and it makes no semantic decision (rule 4).
 *
 * Pure and deterministic: no clock, no I/O, no randomness. `base_t` and the
 * per-event deltas are supplied by the caller, so the same input always yields
 * the same bytes.
 *
 * **Scope A only** — the four SMS-eligible uplink types. It has no layout for
 * the other seven and will refuse them rather than improvise (M8-6, M8-7).
 */
object SmsCodec {

    // ─────────────────────────────── encode ───────────────────────────────

    /**
     * Encodes header ‖ events. This is exactly the byte sequence the MAC covers
     * (`09` §6.6.5) — framing is **not** part of it.
     */
    fun encodePayload(header: BatchHeader, events: List<WireEvent>): ByteArray {
        validateHeader(header, events.size)
        val w = BitWriter()
        writeHeader(w, header)
        var lastSeqDelta = -1
        events.forEach { e ->
            if (e.seqDelta <= lastSeqDelta) {
                throw WireEncodingException(
                    "events must be in strictly ascending seq order; " +
                        "seq_delta ${e.seqDelta} follows $lastSeqDelta"
                )
            }
            lastSeqDelta = e.seqDelta
            writeEvent(w, e)
        }
        return w.toByteArray()
    }

    /** Encodes the complete transport blob: framing ‖ header ‖ events. */
    fun encodeBatch(framing: Framing, header: BatchHeader, events: List<WireEvent>): ByteArray {
        require(framing.mac.size == L.MAC_BYTES) { "mac must be ${L.MAC_BYTES} bytes" }
        validateFraming(framing)
        validateHeader(header, events.size)
        val w = BitWriter()
        w.write(framing.batchId, L.BATCH_ID_BITS)
        w.write(framing.partIndex, L.PART_INDEX_BITS)
        w.write(framing.partTotal, L.PART_TOTAL_BITS)
        w.write(framing.originDeviceId, L.ORIGIN_DEVICE_ID_BITS)
        framing.mac.forEach { w.write(it.toInt() and 0xFF, 8) }
        writeHeader(w, header)
        var lastSeqDelta = -1
        events.forEach { e ->
            if (e.seqDelta <= lastSeqDelta) {
                throw WireEncodingException("events must ascend by seq; ${e.seqDelta} after $lastSeqDelta")
            }
            lastSeqDelta = e.seqDelta
            writeEvent(w, e)
        }
        val out = w.toByteArray()
        if (out.size > L.MAX_BATCH_BYTES) {
            throw WireEncodingException("batch is ${out.size} B, over the ${L.MAX_BATCH_BYTES} B budget")
        }
        return out
    }

    private fun writeHeader(w: BitWriter, h: BatchHeader) {
        w.write(h.protoVersion, L.PROTO_VERSION_BITS)
        w.write(h.deviceId, L.DEVICE_ID_BITS)
        w.write(h.teamId, L.TEAM_ID_BITS)
        w.write(h.agencyId, L.AGENCY_ID_BITS)
        w.write(h.incidentId, L.INCIDENT_ID_BITS)
        w.write(h.schemaVersion, L.SCHEMA_VERSION_BITS)
        w.write(h.baseSeq, L.BASE_SEQ_BITS)
        w.write(h.baseT, L.BASE_T_BITS)
        w.write(h.eventCount, L.EVENT_COUNT_BITS)
    }

    private fun writeEvent(w: BitWriter, e: WireEvent) {
        validateEvent(e)
        w.write(e.type.code, L.EVT_TYPE_BITS)
        w.write(e.seqDelta, L.SEQ_DELTA_BITS)
        w.write(e.tDelta, L.T_DELTA_BITS)
        when (e) {
            is WireEvent.CellStatusReported -> {
                w.write(e.cellIndex, L.CELL_INDEX_BITS)
                w.write(e.status.code, L.STATUS_BITS)
                w.write(e.responderId, L.RESPONDER_ID_BITS)
            }
            is WireEvent.ResourceDeltaReported -> {
                w.write(e.itemId, L.ITEM_ID_BITS)
                w.writeSigned(e.qtyDelta, L.QTY_DELTA_BITS)
                w.write(e.responderId, L.RESPONDER_ID_BITS)
            }
            is WireEvent.TeamStatusReported -> {
                w.write(e.teamStatus.code, L.TEAM_STATUS_BITS)
                w.write(e.responderId, L.RESPONDER_ID_BITS)
            }
            is WireEvent.SurvivorReported -> {
                // presence mask order: triage, rel_lat, rel_lon (09 §6.6.2)
                var mask = 0
                if (e.triage != null) mask = mask or 0b100
                if (e.relLat != null) mask = mask or 0b010
                if (e.relLon != null) mask = mask or 0b001
                w.write(mask, L.PRESENCE_MASK_BITS)
                w.write(e.cellIndex, L.CELL_INDEX_BITS)
                w.write(e.personCount, L.PERSON_COUNT_BITS)
                w.write(e.survivorStatus.code, L.SURVIVOR_STATUS_BITS)
                e.triage?.let { w.write(it.code, L.TRIAGE_BITS) }
                e.relLat?.let { w.writeSigned(it, L.REL_COORD_BITS) }
                e.relLon?.let { w.writeSigned(it, L.REL_COORD_BITS) }
                w.write(e.responderId, L.RESPONDER_ID_BITS)
            }
        }
    }

    // ─────────────────────────────── decode ───────────────────────────────

    /** Decodes framing ‖ header ‖ events. The exact inverse of [encodeBatch]. */
    fun decodeBatch(bytes: ByteArray): WireBatch {
        if (bytes.size > L.MAX_BATCH_BYTES) {
            throw WireDecodingException("blob is ${bytes.size} B, over the ${L.MAX_BATCH_BYTES} B budget")
        }
        val r = BitReader(bytes)
        val batchId = r.readInt(L.BATCH_ID_BITS)
        val partIndex = r.readInt(L.PART_INDEX_BITS)
        val partTotal = r.readInt(L.PART_TOTAL_BITS)
        val originDeviceId = r.readInt(L.ORIGIN_DEVICE_ID_BITS)
        val mac = ByteArray(L.MAC_BYTES) { r.readInt(8).toByte() }
        val framing = Framing(batchId, partIndex, partTotal, originDeviceId, mac)
        validateFraming(framing)

        val header = readHeader(r)
        val events = ArrayList<WireEvent>(header.eventCount)
        var lastSeqDelta = -1
        repeat(header.eventCount) {
            val e = readEvent(r)
            if (e.seqDelta <= lastSeqDelta) {
                throw WireDecodingException("events out of seq order: ${e.seqDelta} after $lastSeqDelta")
            }
            lastSeqDelta = e.seqDelta
            events += e
        }
        r.requireOnlyZeroPaddingLeft()
        return WireBatch(framing, header, events)
    }

    /** Decodes a header ‖ events payload (no framing) — the MAC'd byte sequence. */
    fun decodePayload(bytes: ByteArray): Pair<BatchHeader, List<WireEvent>> {
        val r = BitReader(bytes)
        val header = readHeader(r)
        val events = ArrayList<WireEvent>(header.eventCount)
        var last = -1
        repeat(header.eventCount) {
            val e = readEvent(r)
            if (e.seqDelta <= last) throw WireDecodingException("events out of seq order")
            last = e.seqDelta
            events += e
        }
        r.requireOnlyZeroPaddingLeft()
        return header to events
    }

    private fun readHeader(r: BitReader): BatchHeader {
        val h = BatchHeader(
            protoVersion = r.readInt(L.PROTO_VERSION_BITS),
            deviceId = r.readInt(L.DEVICE_ID_BITS),
            teamId = r.readInt(L.TEAM_ID_BITS),
            agencyId = r.readInt(L.AGENCY_ID_BITS),
            incidentId = r.readInt(L.INCIDENT_ID_BITS),
            schemaVersion = r.readInt(L.SCHEMA_VERSION_BITS),
            baseSeq = r.read(L.BASE_SEQ_BITS),
            baseT = r.read(L.BASE_T_BITS),
            eventCount = r.readInt(L.EVENT_COUNT_BITS),
        )
        if (h.protoVersion != L.PROTO_VERSION) {
            throw WireDecodingException("unsupported proto_version ${h.protoVersion}")
        }
        if (h.eventCount == 0) throw WireDecodingException("event_count must be at least 1")
        return h
    }

    private fun readEvent(r: BitReader): WireEvent {
        val code = r.readInt(L.EVT_TYPE_BITS)
        val seqDelta = r.readInt(L.SEQ_DELTA_BITS)
        val tDelta = r.readInt(L.T_DELTA_BITS)
        return when (code) {
            EventType.CELL_STATUS_REPORTED.code -> WireEvent.CellStatusReported(
                seqDelta, tDelta,
                cellIndex = r.readInt(L.CELL_INDEX_BITS).also(::requireCellIndex),
                status = CellStatus.of(r.readInt(L.STATUS_BITS)),
                responderId = r.readInt(L.RESPONDER_ID_BITS),
            )
            EventType.RESOURCE_DELTA_REPORTED.code -> WireEvent.ResourceDeltaReported(
                seqDelta, tDelta,
                itemId = r.readInt(L.ITEM_ID_BITS),
                qtyDelta = r.readSigned(L.QTY_DELTA_BITS),
                responderId = r.readInt(L.RESPONDER_ID_BITS),
            )
            EventType.TEAM_STATUS_REPORTED.code -> WireEvent.TeamStatusReported(
                seqDelta, tDelta,
                teamStatus = TeamStatus.of(r.readInt(L.TEAM_STATUS_BITS)),
                responderId = r.readInt(L.RESPONDER_ID_BITS),
            )
            EventType.SURVIVOR_REPORTED.code -> {
                val mask = r.readInt(L.PRESENCE_MASK_BITS)
                val cellIndex = r.readInt(L.CELL_INDEX_BITS).also(::requireCellIndex)
                val personCount = r.readInt(L.PERSON_COUNT_BITS)
                val survivorStatus = SurvivorStatus.of(r.readInt(L.SURVIVOR_STATUS_BITS))
                val triage = if (mask and 0b100 != 0) Triage.of(r.readInt(L.TRIAGE_BITS)) else null
                val relLat = if (mask and 0b010 != 0) r.readSigned(L.REL_COORD_BITS) else null
                val relLon = if (mask and 0b001 != 0) r.readSigned(L.REL_COORD_BITS) else null
                WireEvent.SurvivorReported(
                    seqDelta, tDelta, cellIndex, personCount, survivorStatus,
                    triage, relLat, relLon, responderId = r.readInt(L.RESPONDER_ID_BITS),
                )
            }
            else -> throw WireDecodingException(
                "event type code $code has no SMS layout — SCOPE A carries only " +
                    "CELL_STATUS_REPORTED, SURVIVOR_REPORTED, RESOURCE_DELTA_REPORTED, TEAM_STATUS_REPORTED"
            )
        }
    }

    // ───────────────────────────── size and validation ─────────────────────

    /** Exact packed size in bits, without encoding. Used to decide what fits. */
    fun eventBits(e: WireEvent): Int = L.EVENT_PREFIX_BITS + when (e) {
        is WireEvent.CellStatusReported -> L.CELL_INDEX_BITS + L.STATUS_BITS + L.RESPONDER_ID_BITS
        is WireEvent.ResourceDeltaReported -> L.ITEM_ID_BITS + L.QTY_DELTA_BITS + L.RESPONDER_ID_BITS
        is WireEvent.TeamStatusReported -> L.TEAM_STATUS_BITS + L.RESPONDER_ID_BITS
        is WireEvent.SurvivorReported ->
            L.PRESENCE_MASK_BITS + L.CELL_INDEX_BITS + L.PERSON_COUNT_BITS + L.SURVIVOR_STATUS_BITS +
                (if (e.triage != null) L.TRIAGE_BITS else 0) +
                (if (e.relLat != null) L.REL_COORD_BITS else 0) +
                (if (e.relLon != null) L.REL_COORD_BITS else 0) +
                L.RESPONDER_ID_BITS
    }

    fun batchBytes(events: List<WireEvent>): Int =
        (L.FIXED_OVERHEAD_BITS + events.sumOf { eventBits(it) } + 7) / 8

    fun fitsBudget(events: List<WireEvent>): Boolean = batchBytes(events) <= L.MAX_BATCH_BYTES

    private fun requireCellIndex(v: Int) {
        if (v > L.MAX_CELL_INDEX) {
            throw WireDecodingException(
                "cell_index $v exceeds MAX_CELL_INDEX ${L.MAX_CELL_INDEX}" +
                    if (v == L.RESERVED_CELL_INDEX) " (8191 is reserved, never allocated — 09 §10.5)" else ""
            )
        }
    }

    private fun validateFraming(f: Framing) {
        if (f.batchId !in 0..L.MAX_BATCH_ID) throw WireEncodingException("batch_id ${f.batchId} out of range")
        if (f.partIndex !in 1..L.MAX_PART) throw WireEncodingException("part_index ${f.partIndex} out of range")
        if (f.partTotal !in 1..L.MAX_PART) throw WireEncodingException("part_total ${f.partTotal} out of range")
        if (f.partTotal != 1 || f.partIndex != 1) {
            throw WireEncodingException(
                "Level 1 is single-segment only (M8-12): part_index/part_total must be 1/1, " +
                    "got ${f.partIndex}/${f.partTotal}"
            )
        }
        if (f.originDeviceId !in 0..L.MAX_DEVICE_ID) {
            throw WireEncodingException("origin_device_id ${f.originDeviceId} out of range")
        }
    }

    private fun validateHeader(h: BatchHeader, actualCount: Int) {
        fun chk(name: String, v: Long, max: Long) {
            if (v < 0 || v > max) throw WireEncodingException("$name $v out of range 0..$max")
        }
        chk("proto_version", h.protoVersion.toLong(), L.MAX_PROTO_VERSION.toLong())
        chk("device_id", h.deviceId.toLong(), L.MAX_DEVICE_ID.toLong())
        chk("team_id", h.teamId.toLong(), L.MAX_TEAM_ID.toLong())
        chk("agency_id", h.agencyId.toLong(), L.MAX_AGENCY_ID.toLong())
        chk("incident_id", h.incidentId.toLong(), L.MAX_INCIDENT_ID.toLong())
        chk("schema_version", h.schemaVersion.toLong(), L.MAX_SCHEMA_VERSION.toLong())
        chk("base_seq", h.baseSeq, L.MAX_SEQ)
        chk("base_t", h.baseT, L.MAX_BASE_T)
        if (h.eventCount !in 1..L.MAX_EVENT_COUNT) {
            throw WireEncodingException("event_count ${h.eventCount} out of range 1..${L.MAX_EVENT_COUNT}")
        }
        if (h.eventCount != actualCount) {
            throw WireEncodingException("event_count ${h.eventCount} disagrees with $actualCount events")
        }
    }

    private fun validateEvent(e: WireEvent) {
        if (e.seqDelta !in 0..L.MAX_SEQ_DELTA) {
            throw WireEncodingException(
                "seq_delta ${e.seqDelta} exceeds ${L.MAX_SEQ_DELTA}; the event must stay PENDING for a later batch"
            )
        }
        if (e.tDelta !in 0..L.MAX_T_DELTA) {
            throw WireEncodingException(
                "t_delta ${e.tDelta} exceeds ${L.MAX_T_DELTA} s; the event must stay PENDING for a later batch"
            )
        }
        if (e.responderId !in 0..L.MAX_RESPONDER_ID) {
            throw WireEncodingException("responder_id ${e.responderId} out of range")
        }
        when (e) {
            is WireEvent.CellStatusReported -> reqCell(e.cellIndex)
            is WireEvent.ResourceDeltaReported -> {
                if (e.itemId !in 0..L.MAX_ITEM_ID) throw WireEncodingException("item_id ${e.itemId} out of range")
                if (e.qtyDelta !in L.MIN_QTY_DELTA..L.MAX_QTY_DELTA) {
                    throw WireEncodingException("qty_delta ${e.qtyDelta} out of range")
                }
            }
            is WireEvent.TeamStatusReported -> Unit
            is WireEvent.SurvivorReported -> {
                reqCell(e.cellIndex)
                if (e.personCount !in 0..L.MAX_PERSON_COUNT) {
                    throw WireEncodingException("person_count ${e.personCount} out of range")
                }
                e.relLat?.let { if (it !in L.MIN_REL_COORD..L.MAX_REL_COORD) throw WireEncodingException("rel_lat $it out of range") }
                e.relLon?.let { if (it !in L.MIN_REL_COORD..L.MAX_REL_COORD) throw WireEncodingException("rel_lon $it out of range") }
            }
        }
    }

    private fun reqCell(v: Int) {
        if (v !in 0..L.MAX_CELL_INDEX) {
            throw WireEncodingException(
                "cell_index $v out of range 0..${L.MAX_CELL_INDEX}" +
                    if (v == L.RESERVED_CELL_INDEX) " (8191 reserved — 09 §10.5)" else ""
            )
        }
    }
}
