package ai.rescuenet.field

import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.sync.BatchVerdict
import ai.rescuenet.field.sync.JsonBatchCodec
import ai.rescuenet.field.transport.CostClass
import ai.rescuenet.field.transport.InboundBatch
import ai.rescuenet.field.transport.LatencyClass
import ai.rescuenet.field.transport.SendOutcome
import ai.rescuenet.field.transport.SendTicket
import ai.rescuenet.field.transport.Transport
import ai.rescuenet.field.transport.TransportCapabilities
import ai.rescuenet.field.transport.TransportSelector
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

/** `06` §7.3 transport selection, AD-06/AD-07/AD-08. Level U. */
class TransportSelectionTest {

    private class Fake(
        val label: String,
        private val caps: TransportCapabilities,
    ) : Transport {
        var lastBatch: ByteArray? = null
        override fun capabilities() = caps
        override suspend fun send(batch: ByteArray, priority: Priority): Pair<SendTicket, SendOutcome> {
            lastBatch = batch
            return SendTicket(1, "b") to SendOutcome.Evaluated(ByteArray(0))
        }
        override suspend fun receive(): List<InboundBatch> = emptyList()
        override suspend fun acknowledge(inboundIds: List<String>) = Unit
    }

    private fun caps(
        cost: CostClass, latency: LatencyClass, available: Boolean = true, downlink: Boolean = true,
    ) = TransportCapabilities(1024, downlink, latency, cost, true, available)

    private val internet = Fake("internet", caps(CostClass.FREE, LatencyClass.FAST))
    private val smsLike  = Fake("sms", caps(CostClass.METERED, LatencyClass.VERY_SLOW, downlink = false))

    /** Rule 1 — prefer available && FREE && FAST. */
    @Test fun prefersFreeFastWhenAvailable() {
        val s = TransportSelector(listOf(smsLike, internet))
        assertSame(internet, s.select(Priority.ROUTINE))
        assertSame(internet, s.select(Priority.CRITICAL))
    }

    /**
     * **AD-09** — `ROUTINE` is never sent over a METERED VERY_SLOW transport,
     * so with internet gone a ROUTINE event has nowhere to go and stays PENDING
     * (rule 3). `CRITICAL` may use that path.
     */
    @Test fun routineNeverUsesMeteredVerySlowButCriticalMay() {
        val offlineInternet = Fake("internet", caps(CostClass.FREE, LatencyClass.FAST, available = false))
        val s = TransportSelector(listOf(offlineInternet, smsLike))
        assertNull("ROUTINE must stay PENDING (AD-09)", s.select(Priority.ROUTINE))
        assertSame("CRITICAL may use the metered path", smsLike, s.select(Priority.CRITICAL))
    }

    /** Rule 3 — nothing available means no transport, so rows remain PENDING. */
    @Test fun noAvailableTransportSelectsNothing() {
        val s = TransportSelector(listOf(
            Fake("a", caps(CostClass.FREE, LatencyClass.FAST, available = false)),
            Fake("b", caps(CostClass.METERED, LatencyClass.VERY_SLOW, available = false)),
        ))
        assertNull(s.select(Priority.CRITICAL))
        assertNull(s.select(Priority.ROUTINE))
    }

    /**
     * **AD-08** — selection reads declared capabilities only, never name or
     * type. Two transports with identical capabilities but different labels
     * must be treated as interchangeable; a rank tie is resolved without
     * consulting either label.
     */
    @Test fun selectionIsBlindToNameAndType() {
        val a = Fake("zzz-peer", caps(CostClass.FREE, LatencyClass.SLOW))
        val b = Fake("aaa-other", caps(CostClass.FREE, LatencyClass.SLOW))
        val chosen = TransportSelector(listOf(a, b)).select(Priority.ROUTINE)
        assertNotNull(chosen)
        assertTrue("a tie must resolve to one of the equals, by capability not label",
            chosen === a || chosen === b)
        // Improving only the *capabilities* of the alphabetically-later one must flip the choice.
        val faster = Fake("zzz-peer", caps(CostClass.FREE, LatencyClass.FAST))
        assertSame(faster, TransportSelector(listOf(b, faster)).select(Priority.ROUTINE))
    }

    /** AD-06 — a transport receives opaque bytes and never a typed payload. */
    @Test fun transportSendSignatureCarriesOpaqueBytes() {
        // Java reflection: kotlin-reflect is deliberately not on the classpath.
        val send = Transport::class.java.methods.single { it.name == "send" }
        val params = send.parameterTypes.map { it.name }
        assertTrue("batch must be ByteArray (AD-06): \$params", params.any { it == "[B" })
        assertTrue("no domain type may appear in the transport signature: \$params",
            params.none { it.contains("LocalEvent") || it.contains("OutboxRow") || it.contains("EventType") })
    }

    /** `09` §3.4 delta envelope parses, and events keep their server-set fields. */
    @Test fun deltaPageParsesWithServerSetFields() {
        val body = """
            {"events":[{"device_id":9,"seq":1,"type":7,"entity_type":1,"entity_id":214,
                        "payload":{"status":"SEARCHED"},"t_dev":1700000000000,"schema_version":1,
                        "responder_id":9,"team_id":2,"agency_id":0,"incident_id":9,
                        "server_seq":1401,"t_srv":1700000005000,"received_via":1}],
             "next_since":1402,"has_more":true,"current_server_seq":1560}
        """.trimIndent().toByteArray()
        val p = JsonBatchCodec().parseDelta(body)
        assertEquals(1, p.events.size)
        assertEquals(1401L, p.events[0].serverSeq)
        assertEquals(1700000005000L, p.events[0].tSrv)
        assertEquals(1, p.events[0].receivedVia)
        assertEquals(1402L, p.nextSince)
        assertTrue(p.hasMore)
        assertEquals(1560L, p.currentServerSeq)
    }

    /** An empty verdict is well-formed, not an error. */
    @Test fun emptyVerdictParses() {
        val v: BatchVerdict = JsonBatchCodec().parse("""{"accepted":[],"rejected":[]}""".toByteArray())
        assertEquals(0, v.accepted.size)
        assertEquals(0, v.rejected.size)
    }
}
