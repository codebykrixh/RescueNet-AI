package ai.rescuenet.field

import ai.rescuenet.field.codec.*
import ai.rescuenet.field.codec.WireLimits as L
import org.junit.Assert.*
import org.junit.Test

/**
 * **TR-25** — codec round-trip (DM-25, NFR-01) and **TR-26** — never truncates
 * (`08` §10.1 rule 2). Level U, JUnit5 runner, pure JVM.
 */
class CodecRoundTripTest {

    private fun hdr(count: Int, baseSeq: Long = 4021, baseT: Long = 3600) = BatchHeader(
        protoVersion = 1, deviceId = 17, teamId = 3, agencyId = 1,
        incidentId = 9, schemaVersion = 1, baseSeq = baseSeq, baseT = baseT, eventCount = count,
    )
    private fun framing(mac: ByteArray = byteArrayOf(1, 2, 3, 4)) =
        Framing(batchId = 0x9F3A, partIndex = 1, partTotal = 1, originDeviceId = 17, mac = mac)

    private fun roundTrip(events: List<WireEvent>) {
        val blob = SmsCodec.encodeBatch(framing(), hdr(events.size), events)
        val back = SmsCodec.decodeBatch(blob)
        assertEquals("header must round-trip", hdr(events.size), back.header)
        assertEquals("framing must round-trip", framing(), back.framing)
        assertEquals("events must round-trip exactly", events, back.events)
        // Encode(Decode(bytes)) reproduces the canonical bytes.
        assertArrayEquals(blob, SmsCodec.encodeBatch(back.framing, back.header, back.events))
    }

    // ───────────────────────────── TR-25 ─────────────────────────────

    @Test fun tr25_cellStatus_allStatuses() {
        CellStatus.entries.forEachIndexed { i, st ->
            roundTrip(listOf(WireEvent.CellStatusReported(i, i * 7, 214, st, 71)))
        }
    }

    @Test fun tr25_resourceDelta_signedRange() {
        listOf(L.MIN_QTY_DELTA, -1, 0, 1, L.MAX_QTY_DELTA).forEachIndexed { i, q ->
            roundTrip(listOf(WireEvent.ResourceDeltaReported(i, i, 7, q, 84)))
        }
    }

    @Test fun tr25_teamStatus_allStatuses() {
        TeamStatus.entries.forEachIndexed { i, st ->
            roundTrip(listOf(WireEvent.TeamStatusReported(i, i, st, 71)))
        }
    }

    /** All 8 presence-mask combinations must round-trip, absent staying absent. */
    @Test fun tr25_survivor_allPresenceMaskCombinations() {
        var i = 0
        listOf(null, Triage.RED).forEach { tri ->
            listOf(null, 1420).forEach { lat ->
                listOf(null, -880).forEach { lon ->
                    val e = WireEvent.SurvivorReported(i, i, 214, 2, SurvivorStatus.TRAPPED, tri, lat, lon, 71)
                    roundTrip(listOf(e))
                    val back = SmsCodec.decodeBatch(SmsCodec.encodeBatch(framing(), hdr(1), listOf(e))).events[0]
                        as WireEvent.SurvivorReported
                    assertEquals("triage presence", tri, back.triage)
                    assertEquals("rel_lat presence", lat, back.relLat)
                    assertEquals("rel_lon presence", lon, back.relLon)
                    i++
                }
            }
        }
    }

    @Test fun tr25_survivor_signedCoordinateExtremes() {
        listOf(L.MIN_REL_COORD to L.MAX_REL_COORD, L.MAX_REL_COORD to L.MIN_REL_COORD, 0 to 0)
            .forEachIndexed { i, (la, lo) ->
                roundTrip(listOf(WireEvent.SurvivorReported(i, i, 0, 0, SurvivorStatus.DECEASED, Triage.BLACK, la, lo, 0)))
            }
    }

    @Test fun tr25_mixedBatchRoundTrips() {
        roundTrip(listOf(
            WireEvent.SurvivorReported(0, 0, 214, 2, SurvivorStatus.TRAPPED, Triage.RED, 1420, -880, 71),
            WireEvent.CellStatusReported(1, 14, 214, CellStatus.SEARCHED, 71),
            WireEvent.ResourceDeltaReported(2, 20, 7, -2, 71),
            WireEvent.TeamStatusReported(3, 25, TeamStatus.ACTIVE, 71),
        ))
    }

    @Test fun tr25_boundaryValuesRoundTrip() {
        roundTrip(listOf(WireEvent.CellStatusReported(
            seqDelta = L.MAX_SEQ_DELTA, tDelta = L.MAX_T_DELTA,
            cellIndex = L.MAX_CELL_INDEX, status = CellStatus.NEEDS_RESEARCH,
            responderId = L.MAX_RESPONDER_ID)))
        roundTrip(listOf(WireEvent.CellStatusReported(0, 0, 0, CellStatus.IN_PROGRESS, 0)))
    }

    @Test fun tr25_headerBoundaryValues() {
        val h = BatchHeader(15, L.MAX_DEVICE_ID, L.MAX_TEAM_ID, L.MAX_AGENCY_ID,
            L.MAX_INCIDENT_ID, L.MAX_SCHEMA_VERSION, L.MAX_SEQ, L.MAX_BASE_T, 1)
        // proto_version 15 is out-of-contract on decode, so exercise the payload path
        val ev = listOf(WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0))
        val bytes = SmsCodec.encodePayload(h, ev)
        assertTrue(bytes.isNotEmpty())
        val h2 = BatchHeader(1, L.MAX_DEVICE_ID, L.MAX_TEAM_ID, L.MAX_AGENCY_ID,
            L.MAX_INCIDENT_ID, L.MAX_SCHEMA_VERSION, L.MAX_SEQ, L.MAX_BASE_T, 1)
        val (back, evs) = SmsCodec.decodePayload(SmsCodec.encodePayload(h2, ev))
        assertEquals(h2, back); assertEquals(ev, evs)
    }

    // ───────────────────────────── TR-26 ─────────────────────────────

    /** `seq_delta` > 63 is refused, never masked into range. */
    @Test fun tr26_seqDeltaOverflowIsRefusedNotTruncated() {
        val bad = WireEvent.CellStatusReported(64, 0, 214, CellStatus.SEARCHED, 71)
        val ex = assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(bad))
        }
        assertTrue(ex.message!!.contains("seq_delta"))
    }

    /** `t_delta` > 4095 is refused. */
    @Test fun tr26_tDeltaOverflowIsRefusedNotTruncated() {
        val bad = WireEvent.CellStatusReported(0, 4096, 214, CellStatus.SEARCHED, 71)
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(bad))
        }
    }

    /** `cell_index` 8191 is reserved and 8192+ is unrepresentable — both refused. */
    @Test fun tr26_reservedAndOversizedCellIndexRefused() {
        listOf(L.RESERVED_CELL_INDEX, 8192, 99999).forEach { idx ->
            assertThrows("cell_index $idx must be refused", WireEncodingException::class.java) {
                SmsCodec.encodeBatch(framing(), hdr(1), listOf(
                    WireEvent.CellStatusReported(0, 0, idx, CellStatus.SEARCHED, 71)))
            }
        }
    }

    @Test fun tr26_outOfRangeScalarsRefused() {
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(
                WireEvent.ResourceDeltaReported(0, 0, 7, 128, 71)))          // qty_delta > 127
        }
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(
                WireEvent.ResourceDeltaReported(0, 0, 7, -129, 71)))         // qty_delta < -128
        }
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(
                WireEvent.CellStatusReported(0, 0, 0, CellStatus.SEARCHED, 1024)))  // responder_id > 1023
        }
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(1), listOf(
                WireEvent.SurvivorReported(0, 0, 0, 64, SurvivorStatus.TRAPPED, null, null, null, 0)))
        }
    }

    /** The BitWriter refuses an over-wide value outright rather than masking it. */
    @Test fun tr26_bitWriterNeverMasks() {
        assertThrows(WireEncodingException::class.java) { BitWriter().write(8L, 3) }
        assertThrows(WireEncodingException::class.java) { BitWriter().writeSigned(128, 8) }
        assertThrows(WireEncodingException::class.java) { BitWriter().writeSigned(-129, 8) }
    }

    /** `event_count` is 5-bit: more than 31 events is refused. */
    @Test fun tr26_eventCountOver31Refused() {
        val many = (0..31).map { WireEvent.TeamStatusReported(it, 0, TeamStatus.ACTIVE, 0) }
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(many.size), many)
        }
    }

    @Test fun tr26_eventCountMustMatchActualEvents() {
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(5), listOf(
                WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0)))
        }
    }

    // ─────────────────────── ordering, ambiguity, scope ───────────────────

    @Test fun eventsMustAscendBySeq() {
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(framing(), hdr(2), listOf(
                WireEvent.CellStatusReported(5, 0, 1, CellStatus.SEARCHED, 1),
                WireEvent.CellStatusReported(3, 1, 2, CellStatus.SEARCHED, 1)))
        }
    }

    /**
     * A CELL_STATUS batch is 68 + 89 + 48 = 205 bits, so it carries 3 zero
     * padding bits. Setting one of them must be rejected as ambiguous rather
     * than silently accepted. (A TEAM_STATUS batch is exactly 192 bits and has
     * no padding at all, so it cannot exercise this path.)
     */
    @Test fun nonZeroTrailingPaddingIsRejectedAsAmbiguous() {
        val events = listOf(WireEvent.CellStatusReported(0, 0, 214, CellStatus.SEARCHED, 71))
        val blob = SmsCodec.encodeBatch(framing(), hdr(1), events)
        assertEquals("this fixture must have padding bits", 26, blob.size)
        assertEquals("decoding the clean blob must work", events, SmsCodec.decodeBatch(blob).events)

        val tampered = blob.copyOf()
        tampered[tampered.size - 1] = (tampered[tampered.size - 1].toInt() or 0x01).toByte()
        val ex = assertThrows(WireDecodingException::class.java) { SmsCodec.decodeBatch(tampered) }
        assertTrue(ex.message!!.contains("padding"))
    }

    /** A batch that lands exactly on a byte boundary has no padding to check. */
    @Test fun byteAlignedBatchHasNoPaddingBits() {
        val blob = SmsCodec.encodeBatch(framing(), hdr(1), listOf(
            WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0)))
        assertEquals("68 + 89 + 35 = 192 bits = 24 B exactly", 24, blob.size)
    }

    /** SCOPE A: a type code with no SMS layout is refused on decode, not guessed. */
    @Test fun unknownOrNonSmsTypeCodeRejectedOnDecode() {
        val w = BitWriter()
        w.write(1, L.PROTO_VERSION_BITS); w.write(17, L.DEVICE_ID_BITS); w.write(3, L.TEAM_ID_BITS)
        w.write(1, L.AGENCY_ID_BITS); w.write(9, L.INCIDENT_ID_BITS); w.write(1, L.SCHEMA_VERSION_BITS)
        w.write(4021L, L.BASE_SEQ_BITS); w.write(0L, L.BASE_T_BITS); w.write(1, L.EVENT_COUNT_BITS)
        w.write(10, L.EVT_TYPE_BITS)   // POSITION_REPORTED — no SMS layout
        w.write(0, L.SEQ_DELTA_BITS); w.write(0, L.T_DELTA_BITS)
        val ex = assertThrows(WireDecodingException::class.java) { SmsCodec.decodePayload(w.toByteArray()) }
        assertTrue(ex.message!!.contains("no SMS layout"))
    }

    @Test fun levelOneIsSingleSegmentOnly() {
        assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodeBatch(Framing(1, 1, 2, 17, byteArrayOf(1, 2, 3, 4)), hdr(1),
                listOf(WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0)))
        }
    }
}
