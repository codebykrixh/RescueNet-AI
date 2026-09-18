package ai.rescuenet.field

import ai.rescuenet.field.codec.*
import ai.rescuenet.field.codec.WireLimits as L
import ai.rescuenet.field.transport.SmsTransport
import org.junit.Assert.*
import org.junit.Test

/**
 * Known-answer vectors and the arithmetic of `09` §6.6.
 *
 * Every expected value is **derived from the ratified layout**, not invented:
 * each is computed independently inside the test from the documented field
 * widths and then compared with the codec's output. If the codec and the
 * contract ever disagree, one of the two has moved.
 */
class CodecVectorsTest {

    private fun header(count: Int) = BatchHeader(1, 17, 3, 1, 9, 1, 4021L, 3600L, count)

    // ─────────────────────── TR-11: max cell index ───────────────────────

    /**
     * **TR-11 — release-blocking, traces F-01.** Every valid `cell_index`
     * (0…8,190) must round-trip with no collision, wrap or truncation.
     */
    @Test fun tr11_everyValidCellIndexRoundTripsWithNoCollision() {
        val seen = HashSet<Int>(8192)
        for (idx in 0..L.MAX_CELL_INDEX) {
            val e = WireEvent.CellStatusReported(0, 0, idx, CellStatus.SEARCHED, 71)
            val back = SmsCodec.decodePayload(SmsCodec.encodePayload(header(1), listOf(e)))
                .second[0] as WireEvent.CellStatusReported
            assertEquals("index " + idx + " must survive", idx, back.cellIndex)
            assertTrue("collision at " + idx, seen.add(back.cellIndex))
        }
        assertEquals("all 8,191 valid indices distinct", 8191, seen.size)
    }

    @Test fun tr11_reservedIndex8191IsRefused() {
        val ex = assertThrows(WireEncodingException::class.java) {
            SmsCodec.encodePayload(header(1), listOf(
                WireEvent.CellStatusReported(0, 0, L.RESERVED_CELL_INDEX, CellStatus.SEARCHED, 71)))
        }
        assertTrue(ex.message!!.contains("8191") || ex.message!!.contains("reserved"))
    }

    @Test fun tr11_cellIndexFieldIs13Bits() {
        assertEquals(13, L.CELL_INDEX_BITS)
        assertEquals(8190, L.MAX_CELL_INDEX)
        assertEquals("8191 must be exactly 2^13 - 1", (1 shl L.CELL_INDEX_BITS) - 1, L.RESERVED_CELL_INDEX)
    }

    // ─────────────────── TR-12: parametric GRID_GENERATED ─────────────────

    /**
     * **TR-12 (DM-10, FR-203/204).** The Kotlin side asserts the SMS
     * consequence of the parametric grid: `GRID_GENERATED` is not SMS-eligible
     * under SCOPE A, and every index a parametric grid can produce fits the
     * 13-bit field.
     */
    @Test fun tr12_gridGeneratedIsNotSmsEligibleAndGridFitsTheField() {
        val mapper = WireEventMapper()
        assertFalse("GRID_GENERATED has no SMS layout (SCOPE A)",
            ai.rescuenet.field.domain.EventType.GRID_GENERATED in mapper.smsEligible)
        listOf(1 to 1, 25 to 200, 89 to 92, 1 to 8191).forEach { (rows, cols) ->
            val cells = rows * cols
            assertTrue("grid must not exceed MAX_CELLS", cells <= L.MAX_CELL_INDEX + 1)
            assertTrue("max index must fit 13 bits", cells - 1 <= L.MAX_CELL_INDEX)
        }
    }

    // ───────────────────────── known-answer vectors ───────────────────────

    @Test fun vector_headerIs89BitsAnd12Bytes() {
        assertEquals(89, L.HEADER_BITS)
        val payload = SmsCodec.encodePayload(header(1), listOf(
            WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0)))
        assertEquals(124, L.HEADER_BITS + 35)
        assertEquals(16, payload.size)
    }

    @Test fun vector_headerBitPatternMatchesTheRatifiedFieldOrder() {
        val h = BatchHeader(1, 17, 3, 1, 9, 1, 4021L, 3600L, 1)
        val ev = listOf(WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 0))
        val actual = SmsCodec.encodePayload(h, ev)
        val w = BitWriter()
        w.write(1, 4); w.write(17, 12); w.write(3, 8); w.write(1, 4); w.write(9, 12)
        w.write(1, 4); w.write(4021L, 20); w.write(3600L, 20); w.write(1, 5)
        w.write(11, 4); w.write(0, 6); w.write(0, 12); w.write(0, 3); w.write(0, 10)
        assertArrayEquals("codec output must equal an independent pack of the same field order",
            w.toByteArray(), actual)
    }

    /**
     * **Cross-language known-answer vector.** The same header and event packed
     * by the Python side (`backend/src/rescuenet/codec`) must produce these
     * exact bytes. Both implementations are locked to this vector, so a width
     * or field-order drift on either side fails here.
     */
    @Test fun vector_matchesThePythonImplementationByteForByte() {
        val h = BatchHeader(1, 17, 3, 1, 9, 1, 4021L, 3600L, 1)
        val ev = listOf(WireEvent.CellStatusReported(0, 0, 214, CellStatus.SEARCHED, 71))
        val hex = SmsCodec.encodePayload(h, ev).joinToString("") { "%02x".format(it) }
        assertEquals("Kotlin and Python must pack identically",
            "1011031009100fb500e100b800000d622380", hex)
    }

    @Test fun vector_eventBitLengthsMatchTheContract() {
        assertEquals(48, SmsCodec.eventBits(WireEvent.CellStatusReported(0, 0, 1, CellStatus.SEARCHED, 1)))
        assertEquals(48, SmsCodec.eventBits(WireEvent.ResourceDeltaReported(0, 0, 1, 1, 1)))
        assertEquals(35, SmsCodec.eventBits(WireEvent.TeamStatusReported(0, 0, TeamStatus.ACTIVE, 1)))
        assertEquals(57, SmsCodec.eventBits(
            WireEvent.SurvivorReported(0, 0, 1, 1, SurvivorStatus.TRAPPED, null, null, null, 1)))
        assertEquals(92, SmsCodec.eventBits(
            WireEvent.SurvivorReported(0, 0, 1, 1, SurvivorStatus.TRAPPED, Triage.RED, 1, 1, 1)))
    }

    @Test fun vector_ackIsExactlyThreeBytes() {
        val bytes = AckCodec.encode(SmsAck(1, 4022))
        assertEquals(3, bytes.size)
        assertEquals(24, L.ACK_BITS)
        val w = BitWriter(); w.write(1, 4); w.write(4022L, 20)
        assertArrayEquals(w.toByteArray(), bytes)
        assertEquals(SmsAck(1, 4022), AckCodec.decode(bytes))
    }

    @Test fun vector_macIsFirstFourBytesOfHmacSha256OverHeaderAndEvents() {
        val secret = ByteArray(32) { it.toByte() }
        val payload = SmsCodec.encodePayload(header(1), listOf(
            WireEvent.CellStatusReported(0, 0, 214, CellStatus.SEARCHED, 71)))
        val full = BatchMac.full(secret, payload)
        val mac = BatchMac.compute(secret, payload)
        assertEquals(32, full.size)
        assertEquals(4, mac.size)
        assertArrayEquals("truncation must take the LEADING 4 bytes", full.copyOf(4), mac)
        assertTrue(BatchMac.verify(secret, payload, mac))
    }

    // ───────────────────────── transport arithmetic ───────────────────────

    @Test fun transport_120BytesIsExactly160Base64UrlCharactersWithNoPadding() {
        val blob = ByteArray(L.MAX_BATCH_BYTES) { it.toByte() }
        val text = SmsTransport.encodeToText(blob)
        assertEquals("120 B must encode to exactly 160 chars", 160, text.length)
        assertFalse("base64url must be unpadded", text.contains("="))
        assertEquals(SmsTransport.SINGLE_SEGMENT_CHARS, text.length)
        assertArrayEquals(blob, SmsTransport.decodeFromText(text))
    }

    /**
     * base64url uses only `A-Z a-z 0-9 - _`. Every one of those 64 characters is
     * in the GSM 03.38 default alphabet and costs a single septet, so the
     * message never needs an escape and never silently doubles in length.
     */
    @Test fun transport_base64UrlUsesOnlyGsm7SingleSeptetCharacters() {
        val allowed = ('A'..'Z').toSet() + ('a'..'z').toSet() + ('0'..'9').toSet() + setOf('-', '_')
        assertEquals(64, allowed.size)
        val blob = ByteArray(120) { (it * 17).toByte() }
        SmsTransport.encodeToText(blob).forEach {
            assertTrue("character must be base64url and GSM-7 single-septet", it in allowed)
        }
    }

    @Test fun transport_noLevelOnePayloadExceeds120Bytes() {
        assertEquals(157, L.FIXED_OVERHEAD_BITS)
        assertEquals(803, L.EVENT_CAPACITY_BITS)
        listOf(35 to 22, 48 to 16, 57 to 14, 92 to 8).forEach { (bits, expected) ->
            assertEquals("events per 120 B batch", expected, L.EVENT_CAPACITY_BITS / bits)
        }
    }

    @Test fun transport_maxPackingsStayWithinBudgetAndOneSegment() {
        val packs = listOf<Pair<Int, (Int) -> WireEvent>>(
            22 to { i -> WireEvent.TeamStatusReported(i, i, TeamStatus.ACTIVE, 1) },
            16 to { i -> WireEvent.CellStatusReported(i, i, 214, CellStatus.SEARCHED, 71) },
            8 to { i -> WireEvent.SurvivorReported(i, i, 214, 2, SurvivorStatus.TRAPPED, Triage.RED, 1420, -880, 71) },
        )
        packs.forEach { (n, mk) ->
            val events = (0 until n).map(mk)
            assertTrue("events must fit", SmsCodec.fitsBudget(events))
            val blob = SmsCodec.encodeBatch(Framing(1, 1, 1, 17, byteArrayOf(1, 2, 3, 4)), header(n), events)
            assertTrue("blob must be within 120 B", blob.size <= L.MAX_BATCH_BYTES)
            assertTrue("must stay single-segment",
                SmsTransport.encodeToText(blob).length <= SmsTransport.SINGLE_SEGMENT_CHARS)
            assertEquals(events, SmsCodec.decodeBatch(blob).events)
        }
    }

    @Test fun transport_oneEventPastCapacityDoesNotFit() {
        val events = (0..22).map { WireEvent.TeamStatusReported(it, it, TeamStatus.ACTIVE, 1) }
        assertFalse("23 team-status events must not fit", SmsCodec.fitsBudget(events))
    }
}
