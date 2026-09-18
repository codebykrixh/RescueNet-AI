package ai.rescuenet.field

import ai.rescuenet.field.codec.*
import ai.rescuenet.field.codec.WireLimits as L
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.transport.*
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Test

/** MAC, ACK, SMS eligibility and transport-boundary behaviour. Level U. */
class SmsBoundaryTest {

    private val secret = ByteArray(32) { (it * 3).toByte() }
    private fun header(n: Int) = BatchHeader(1, 17, 3, 1, 9, 1, 4021L, 3600L, n)
    private val events = listOf(WireEvent.CellStatusReported(0, 0, 214, CellStatus.SEARCHED, 71))
    private fun payload() = SmsCodec.encodePayload(header(1), events)

    // ─────────────────────────────── MAC ───────────────────────────────

    @Test fun mac_validIsAccepted() {
        val p = payload()
        assertTrue(BatchMac.verify(secret, p, BatchMac.compute(secret, p)))
    }

    @Test fun mac_alteredPayloadIsRejected() {
        val p = payload()
        val mac = BatchMac.compute(secret, p)
        val tampered = p.copyOf().also { it[it.size - 2] = (it[it.size - 2].toInt() xor 0x04).toByte() }
        assertFalse("a tampered payload must fail verification", BatchMac.verify(secret, tampered, mac))
    }

    @Test fun mac_alteredHeaderIsRejected() {
        val p = payload()
        val mac = BatchMac.compute(secret, p)
        val tampered = p.copyOf().also { it[1] = (it[1].toInt() xor 0x01).toByte() }  // inside device_id
        assertFalse("DM-23: the header is covered, so altering it must fail", BatchMac.verify(secret, tampered, mac))
    }

    @Test fun mac_wrongSecretIsRejected() {
        val p = payload()
        val mac = BatchMac.compute(secret, p)
        assertFalse(BatchMac.verify(ByteArray(32) { 0x5A }, p, mac))
    }

    @Test fun mac_missingOrWrongLengthIsRejected() {
        val p = payload()
        assertFalse(BatchMac.verify(secret, p, ByteArray(0)))
        assertFalse(BatchMac.verify(secret, p, ByteArray(3)))
        assertFalse(BatchMac.verify(secret, p, ByteArray(32)))
    }

    /**
     * Framing is deliberately outside the MAC (M8-10). Altering `batch_id`
     * therefore leaves the MAC valid — this asserts the ratified boundary
     * rather than a stronger one nobody agreed to.
     */
    @Test fun mac_framingIsNotCovered() {
        val p = payload()
        val mac = BatchMac.compute(secret, p)
        val a = SmsCodec.encodeBatch(Framing(0x1111, 1, 1, 17, mac), header(1), events)
        val b = SmsCodec.encodeBatch(Framing(0x2222, 1, 1, 17, mac), header(1), events)
        assertFalse("different framing must produce different bytes", a.contentEquals(b))
        listOf(a, b).forEach {
            val d = SmsCodec.decodeBatch(it)
            assertTrue("the MAC stays valid because framing is excluded",
                BatchMac.verify(secret, SmsCodec.encodePayload(d.header, d.events), d.framing.mac))
        }
    }

    // ─────────────────────────────── ACK ───────────────────────────────

    @Test fun ack_roundTripsAcrossTheFullSeqRange() {
        listOf(0L, 1L, 4022L, L.MAX_SEQ).forEach {
            assertEquals(SmsAck(1, it), AckCodec.decode(AckCodec.encode(SmsAck(1, it))))
        }
    }

    @Test fun ack_rejectsOutOfRangeSeq() {
        assertThrows(WireEncodingException::class.java) { AckCodec.encode(SmsAck(1, L.MAX_SEQ + 1)) }
        assertThrows(WireEncodingException::class.java) { AckCodec.encode(SmsAck(1, -1)) }
    }

    @Test fun ack_rejectsWrongLengthAndUnknownProto() {
        assertThrows(WireDecodingException::class.java) { AckCodec.decode(ByteArray(2)) }
        assertThrows(WireDecodingException::class.java) { AckCodec.decode(ByteArray(4)) }
        val w = BitWriter(); w.write(9, 4); w.write(1L, 20)   // proto 9
        assertThrows(WireDecodingException::class.java) { AckCodec.decode(w.toByteArray()) }
    }

    /** Monotonic: lower or equal is a no-op; only higher advances. */
    @Test fun ack_isMonotonic() {
        assertEquals(4022L, AckCodec.advance(4022L, SmsAck(1, 4000)))
        assertEquals(4022L, AckCodec.advance(4022L, SmsAck(1, 4022)))
        assertEquals(4030L, AckCodec.advance(4022L, SmsAck(1, 4030)))
        assertEquals(0L, AckCodec.advance(0L, SmsAck(1, 0)))
    }

    @Test fun ack_replayIsHarmless() {
        var w = 0L
        repeat(3) { w = AckCodec.advance(w, SmsAck(1, 100)) }
        assertEquals(100L, w)
        repeat(3) { w = AckCodec.advance(w, SmsAck(1, 50)) }
        assertEquals("a replayed lower ACK must not rewind", 100L, w)
    }

    // ───────────────────── SMS eligibility (SCOPE A, M8-6/M8-7) ────────────

    private fun ev(type: EventType, payload: String) = LocalEvent(
        deviceId = 17, seq = 4021, type = type.code, entityType = 1, entityId = 214,
        payload = payload, tDev = 1_700_000_000_000, schemaVersion = 1,
        responderId = 71, teamId = 3, agencyId = 1, incidentId = 9)

    @Test fun onlyTheFourRatifiedTypesAreSmsEligible() {
        val m = WireEventMapper()
        assertEquals(setOf(
            EventType.CELL_STATUS_REPORTED, EventType.SURVIVOR_REPORTED,
            EventType.RESOURCE_DELTA_REPORTED, EventType.TEAM_STATUS_REPORTED), m.smsEligible)
        assertEquals(4, m.smsEligible.size)
    }

    /** **M8-7 — absolute.** POSITION_REPORTED can never enter the SMS path. */
    @Test fun positionReportedIsNeverSmsEligible() {
        val m = WireEventMapper()
        val e = ev(EventType.POSITION_REPORTED, """{"rel_lat":10,"rel_lon":20}""")
        assertFalse(m.isSmsEligible(e))
        val ex = assertThrows(WireEncodingException::class.java) { m.toWire(e, 0, 0) }
        assertTrue(ex.message!!.contains("never sent over SMS"))
    }

    @Test fun theSixServerAuthoredTypesHaveNoSmsLayout() {
        val m = WireEventMapper()
        listOf(EventType.INCIDENT_DECLARED, EventType.GRID_GENERATED, EventType.TEAM_REGISTERED,
               EventType.DEVICE_ENROLLED, EventType.ASSIGNMENT_ISSUED, EventType.ASSIGNMENT_REVOKED)
            .forEach {
                assertFalse(it.name, m.isSmsEligible(ev(it, "{}")))
                assertThrows(it.name, WireEncodingException::class.java) { m.toWire(ev(it, "{}"), 0, 0) }
            }
    }

    @Test fun mapperCarriesPayloadFieldsFaithfully() {
        val m = WireEventMapper()
        val w = m.toWire(ev(EventType.SURVIVOR_REPORTED,
            """{"cell_index":214,"person_count":2,"survivor_status":"TRAPPED","triage":"RED","rel_lat":1420,"rel_lon":-880}"""),
            2, 161) as WireEvent.SurvivorReported
        assertEquals(214, w.cellIndex); assertEquals(2, w.personCount)
        assertEquals(SurvivorStatus.TRAPPED, w.survivorStatus); assertEquals(Triage.RED, w.triage)
        assertEquals(1420, w.relLat); assertEquals(-880, w.relLon)
        assertEquals(2, w.seqDelta); assertEquals(161, w.tDelta); assertEquals(71, w.responderId)
    }

    /** `note` is outside the SMS representation by contract, so it is simply not carried. */
    @Test fun teamStatusNoteIsNotCarriedOverSms() {
        val w = WireEventMapper().toWire(
            ev(EventType.TEAM_STATUS_REPORTED, """{"team_status":"ACTIVE","note":"regrouping at the north ridge"}"""),
            0, 0) as WireEvent.TeamStatusReported
        assertEquals(TeamStatus.ACTIVE, w.teamStatus)
        assertEquals("no note field exists on the wire type", 35, SmsCodec.eventBits(w))
    }

    @Test fun mapperRejectsUnknownEnumValues() {
        assertThrows(WireEncodingException::class.java) {
            WireEventMapper().toWire(ev(EventType.CELL_STATUS_REPORTED,
                """{"cell_index":1,"status":"NOT_A_STATUS"}"""), 0, 0)
        }
    }

    // ───────────────────────── SmsTransport behaviour ─────────────────────

    private class FakeSender(var accept: Boolean = true) : SmsSender {
        val sent = mutableListOf<Pair<String, String>>()
        override fun sendText(destination: String, body: String): Boolean {
            sent += destination to body; return accept
        }
    }

    @Test fun capabilitiesAreVerySlowMeteredAnd120Bytes() {
        val c = SmsTransport("+10000000000", FakeSender()).capabilities()
        assertEquals(LatencyClass.VERY_SLOW, c.latencyClass)
        assertEquals(CostClass.METERED, c.costClass)
        assertEquals(120, c.maxBatchBytes)
        assertTrue("downlink is ACK-only but present (D-06)", c.supportsDownlink)
    }

    /** AD-09 via M7's selector: ROUTINE must not ride this link when it is the only one. */
    @Test fun routineNeverSelectsSmsButCriticalMay() {
        val sms = SmsTransport("+10000000000", FakeSender())
        val sel = TransportSelector(listOf(sms))
        assertNull("ROUTINE must stay PENDING (AD-09)", sel.select(Priority.ROUTINE))
        assertSame("CRITICAL may use the metered path", sms, sel.select(Priority.CRITICAL))
    }

    @Test fun sendRefusesAnOverBudgetBlobRatherThanTruncating() = runTest {
        val f = FakeSender()
        val (_, outcome) = SmsTransport("+10000000000", f).send(ByteArray(121), Priority.CRITICAL)
        assertTrue(outcome is SendOutcome.RequestFailed)
        assertFalse("nothing may be transmitted", f.sent.isNotEmpty())
        assertTrue((outcome as SendOutcome.RequestFailed).detail!!.contains("exceeds"))
    }

    @Test fun sendEmitsExactlyOneSingleSegmentTextMessage() = runTest {
        val f = FakeSender()
        SmsTransport("+10000000000", f).send(ByteArray(120) { it.toByte() }, Priority.CRITICAL)
        assertEquals(1, f.sent.size)
        assertEquals(160, f.sent[0].second.length)
        assertFalse(f.sent[0].second.contains("="))
    }

    /** A hand-off failure is retryable so DM-56's SMS backoff applies; no retry lives here. */
    @Test fun senderRefusalIsRetryableAtRequestLevel() = runTest {
        val (_, outcome) = SmsTransport("+1", FakeSender(accept = false)).send(ByteArray(10), Priority.CRITICAL)
        assertTrue((outcome as SendOutcome.RequestFailed).retryableAtRequestLevel)
    }

    @Test fun inboundAckIsParsedFromBase64UrlText() = runTest {
        val t = SmsTransport("+1", FakeSender())
        t.onInboundText(SmsTransport.encodeToText(AckCodec.encode(SmsAck(1, 4022))))
        val batches = t.receive()
        assertEquals(1, batches.size)
        assertEquals(SmsAck(1, 4022), t.parseAck(batches[0].bytes))
    }

    @Test fun malformedInboundTextIsIgnoredNotThrown() = runTest {
        val t = SmsTransport("+1", FakeSender())
        t.onInboundText("!!! not base64 !!!")
        assertTrue(t.receive().isEmpty())
    }
}
