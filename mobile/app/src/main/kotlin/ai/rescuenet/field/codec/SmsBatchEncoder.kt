package ai.rescuenet.field.codec

import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.sync.BatchEncoder
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.OutboxRow
import kotlin.random.Random

/**
 * Turns outbox rows into a packed SMS blob — the M8 implementation of M7's
 * [BatchEncoder] seam.
 *
 * It lives in the **codec** package, not `sync`, so that no package above the
 * transport boundary holds SMS knowledge. `06` §8: *"All SMS-specific knowledge
 * lives here and nowhere else."* The sync layer sees only the abstract
 * [BatchEncoder] interface it declared for M8 to fill.
 *
 * It performs **no retry, no state transition and no priority policy**: the
 * outbox DAO already orders CRITICAL first (`06` §5.3) and M7's
 * [ai.rescuenet.field.sync.OutboxEngine] owns every transition. This class only
 * decides *what fits* and produces bytes.
 *
 * **Nothing is ever truncated.** An event that cannot be represented — wrong
 * type, `seq_delta` > 63, `t_delta` > 4095 s, or simply no room left in the
 * 120 B budget — is **excluded from this batch and left `PENDING`**
 * (`08` §10.1 rule 2). Ordering is preserved; nothing is merged or synthesised.
 *
 * `base_t` is *seconds since incident start*, so the incident epoch must be
 * supplied. [fromEventLog] resolves it from `INCIDENT_DECLARED.started_at` in the
 * device's own event log — the same event, and the same ISO string, the backend
 * reads when it recomputes the MAC. No new table and no schema change: M7's
 * delta pull already puts that event in the log.
 */
class SmsBatchEncoder(
    private val incidentStartEpochSec: () -> Long,
    private val hmacSecret: () -> ByteArray?,
    private val mapper: WireEventMapper = WireEventMapper(),
    private val random: Random = Random.Default,
) : BatchEncoder {

    /** What could not be packed, and why — for diagnostics, never for silent loss. */
    data class Excluded(val row: OutboxRow, val reason: String)

    data class Packed(
        val blob: ByteArray,
        val included: List<OutboxRow>,
        val excluded: List<Excluded>,
    ) {
        override fun equals(other: Any?) = this === other ||
            (other is Packed && blob.contentEquals(other.blob) &&
                included == other.included && excluded == other.excluded)
        override fun hashCode() = (blob.contentHashCode() * 31 + included.hashCode()) * 31 + excluded.hashCode()
    }

    /**
     * M7 calls this to trim candidates to the transport's declared budget. The
     * authoritative decision is made in [pack], which knows each event's real
     * bit cost; this is the cheap upper bound.
     */
    override fun fit(rows: List<OutboxRow>, maxBatchBytes: Int): List<OutboxRow> {
        if (rows.isEmpty()) return rows
        val capacityBits = maxBatchBytes * 8 - WireLimits.FIXED_OVERHEAD_BITS
        if (capacityBits <= 0) return emptyList()
        val maxByBits = capacityBits / MIN_EVENT_BITS
        return rows.take(minOf(maxByBits, WireLimits.MAX_EVENT_COUNT))
    }

    override suspend fun encode(rows: List<OutboxRow>, db: FieldDatabase): ByteArray =
        pack(rows, db).blob

    /**
     * Packs greedily in the order given — which the DAO has already sorted
     * CRITICAL-first — and reports precisely what was left behind.
     */
    suspend fun pack(rows: List<OutboxRow>, db: FieldDatabase): Packed {
        val secret = hmacSecret()
            ?: throw WireEncodingException("no hmac_secret: the device must enrol before using SMS (09 §8)")
        val incidentStart = incidentStartEpochSec()

        val loaded = rows.mapNotNull { r -> db.events().find(r.deviceId, r.seq)?.let { r to it } }
        if (loaded.isEmpty()) throw WireEncodingException("no events found for the given outbox rows")

        // Ordering: ascending seq. 08 §10.1 rule 3 forbids reordering as a
        // representation change, but the batch must be built in seq order for
        // seq_delta to be meaningful; the DAO already yields ascending seq per device.
        val ordered = loaded.sortedBy { it.second.seq }
        val first = ordered.first().second
        val baseSeq = first.seq
        val baseT = ((first.tDev / 1000) - incidentStart).coerceAtLeast(0)
        if (baseT > WireLimits.MAX_BASE_T) {
            throw WireEncodingException("base_t $baseT exceeds the 20-bit range; incident epoch too old")
        }

        val included = ArrayList<OutboxRow>()
        val excluded = ArrayList<Excluded>()
        val wire = ArrayList<WireEvent>()
        var usedBits = WireLimits.FIXED_OVERHEAD_BITS

        for ((row, ev) in ordered) {
            if (wire.size >= WireLimits.MAX_EVENT_COUNT) {
                excluded += Excluded(row, "batch already holds ${WireLimits.MAX_EVENT_COUNT} events (event_count is 5-bit)")
                continue
            }
            val we = try {
                mapper.toWire(ev, seqDelta = seqDeltaOf(ev, baseSeq), tDelta = tDeltaOf(ev, incidentStart, baseT))
            } catch (e: WireEncodingException) {
                excluded += Excluded(row, e.message ?: "not representable"); continue
            }
            val cost = SmsCodec.eventBits(we)
            if (usedBits + cost > WireLimits.MAX_BATCH_BYTES * 8) {
                excluded += Excluded(row, "does not fit the remaining ${WireLimits.MAX_BATCH_BYTES}-byte budget")
                continue
            }
            usedBits += cost
            wire += we
            included += row
        }

        if (wire.isEmpty()) throw WireEncodingException("no event in this selection can be represented over SMS")

        val header = BatchHeader(
            protoVersion = WireLimits.PROTO_VERSION,
            deviceId = first.deviceId, teamId = first.teamId, agencyId = first.agencyId,
            incidentId = first.incidentId, schemaVersion = first.schemaVersion,
            baseSeq = baseSeq, baseT = baseT, eventCount = wire.size,
        )
        // MAC covers header ‖ events only — framing excluded (09 §6.6.5).
        val macInput = SmsCodec.encodePayload(header, wire)
        val mac = BatchMac.compute(secret, macInput)
        val framing = Framing(
            batchId = random.nextInt(0, WireLimits.MAX_BATCH_ID + 1),
            partIndex = 1, partTotal = 1,                       // single-segment, M8-12
            originDeviceId = first.deviceId, mac = mac,
        )
        return Packed(SmsCodec.encodeBatch(framing, header, wire), included, excluded)
    }

    private fun seqDeltaOf(e: LocalEvent, baseSeq: Long): Int {
        val d = e.seq - baseSeq
        if (d < 0 || d > WireLimits.MAX_SEQ_DELTA) {
            throw WireEncodingException("seq_delta $d exceeds ${WireLimits.MAX_SEQ_DELTA}; event stays PENDING")
        }
        return d.toInt()
    }

    private fun tDeltaOf(e: LocalEvent, incidentStart: Long, baseT: Long): Int {
        val d = ((e.tDev / 1000) - incidentStart) - baseT
        if (d < 0 || d > WireLimits.MAX_T_DELTA) {
            throw WireEncodingException("t_delta $d exceeds ${WireLimits.MAX_T_DELTA} s; event stays PENDING")
        }
        return d.toInt()
    }

    companion object {
        /** Cheapest representable event: TEAM_STATUS_REPORTED, 35 b. */
        internal const val MIN_EVENT_BITS = 35

        /**
         * The live wiring: resolve the incident epoch from the local event log.
         *
         * Throws if `INCIDENT_DECLARED` has not been received yet, which is the
         * correct outcome — the batch is not built and its events stay
         * `PENDING`. A guessed epoch would corrupt `base_t` and every MAC.
         */
        suspend fun fromEventLog(
            db: FieldDatabase,
            incidentId: Int,
            credentials: () -> ByteArray?,
        ): SmsBatchEncoder {
            val epoch = IncidentEpoch(db).providerFor(incidentId)
            return SmsBatchEncoder(incidentStartEpochSec = epoch, hmacSecret = credentials)
        }
    }
}
