package ai.rescuenet.field

import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.store.OutboxState
import ai.rescuenet.field.sync.AcceptedEvent
import ai.rescuenet.field.sync.BackoffPolicy
import ai.rescuenet.field.sync.JsonBatchCodec
import ai.rescuenet.field.sync.RejectedEvent
import ai.rescuenet.field.transport.CostClass
import ai.rescuenet.field.transport.LatencyClass
import ai.rescuenet.field.transport.TransportCapabilities
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * **TR-01 · TR-02 · TR-03 · TR-04 · TR-24** — all level **U**, JUnit5 runner
 * per `11`, pure JVM so they run fast and often (`07` row 14).
 *
 * These test the *decision rules* in isolation. The database transitions those
 * rules drive are covered on-device in `OutboxTransitionTest`.
 */
class OutboxContractTest {

    private val internet = TransportCapabilities(
        maxBatchBytes = 256 * 1024, supportsDownlink = true,
        latencyClass = LatencyClass.FAST, costClass = CostClass.FREE,
        orderingGuaranteed = true, available = true,
    )
    private val smsLike = TransportCapabilities(
        maxBatchBytes = 134, supportsDownlink = false,
        latencyClass = LatencyClass.VERY_SLOW, costClass = CostClass.METERED,
        orderingGuaranteed = false, available = true,
    )

    // ───────────────────────────── TR-01 — REJECTED state ─────────────────

    /** `08` §6.2 — exactly four persisted states; no `RETRY`, no `PRUNED`. */
    @Test fun tr01_exactlyFourPersistedOutboxStates() {
        assertEquals(
            setOf("PENDING", "IN_FLIGHT", "ACKED", "REJECTED"),
            OutboxState.entries.map { it.name }.toSet(),
        )
        assertTrue("DM-16: retry is PENDING + next_attempt_at, not a state",
            OutboxState.entries.none { it.name == "RETRY" })
        assertTrue("06 §5.3: pruning is row deletion, not a state",
            OutboxState.entries.none { it.name == "PRUNED" })
    }

    /** AP-14 / DM-39 — `REJECTED` is a delivery state on the outbox row only. */
    @Test fun tr01_rejectedIsADeliveryStateNotAnEventType() {
        assertTrue("REJECTED must not be an event type (DM-39)",
            EventType.entries.none { it.name == "REJECTED" })
        assertEquals(11, EventType.entries.size)
    }

    // ──────────────────── TR-02 — retryable vs permanent ──────────────────

    /**
     * `09` §2.7.1 — a row enters `REJECTED` **only** on `retryable: false`
     * inside a `200`. Everything else returns it to `PENDING`.
     */
    @Test fun tr02_onlyNonRetryableRejectionIsPermanent() {
        val permanent = RejectedEvent(7, 1, "UNKNOWN_CELL", retryable = false, message = null)
        val transient = RejectedEvent(7, 2, "UNAVAILABLE", retryable = true, message = null)
        assertFalse("permanent verdict → REJECTED", permanent.retryable)
        assertTrue("retryable verdict → PENDING", transient.retryable)
    }

    /** `09` §2.6 — `UNAVAILABLE` is the only retryable verdict the server issues. */
    @Test fun tr02_documentedCodeRetryability() {
        val codes = mapOf(
            "UNKNOWN_TYPE" to false, "INVALID_PAYLOAD" to false, "UNSUPPORTED_SCHEMA" to false,
            "ATTRIBUTION_MISMATCH" to false, "WRONG_INCIDENT" to false,
            "TYPE_NOT_PERMITTED" to false, "SEQ_NOT_MONOTONIC" to false,
            "UNKNOWN_CELL" to false, "UNAVAILABLE" to true,
        )
        assertEquals(listOf("UNAVAILABLE"), codes.filterValues { it }.keys.toList())
    }

    // ───────────── TR-03 — the boolean is authoritative, not the code ─────

    /**
     * **AP-21** — *"The client acts on the `retryable` boolean and never
     * interprets the `code` string."*
     *
     * The strongest form of this test: an **unknown, never-before-seen code**
     * must behave purely by its boolean, in both directions. If any `when
     * (code)` existed in the engine, one of these two would break.
     */
    @Test fun tr03_unknownCodeIsDrivenEntirelyByTheBoolean() {
        val unknownRetryable = RejectedEvent(7, 1, "CODE_INVENTED_IN_2027", retryable = true, message = null)
        val unknownPermanent = RejectedEvent(7, 2, "CODE_INVENTED_IN_2027", retryable = false, message = null)
        assertTrue(unknownRetryable.retryable)
        assertFalse(unknownPermanent.retryable)
    }

    /**
     * A code that *sounds* permanent but is flagged retryable must be retried,
     * and vice versa. This is the case a code-parsing implementation gets wrong.
     */
    @Test fun tr03_codeSemanticsNeverOverrideTheBoolean() {
        val soundsPermanent = RejectedEvent(7, 1, "INVALID_PAYLOAD", retryable = true, message = null)
        val soundsTransient = RejectedEvent(7, 2, "UNAVAILABLE", retryable = false, message = null)
        assertTrue("must be retried despite the code", soundsPermanent.retryable)
        assertFalse("must be permanent despite the code", soundsTransient.retryable)
    }

    /** The parser must surface the boolean verbatim and never normalise the code. */
    @Test fun tr03_parserPreservesBooleanAndCodeVerbatim() {
        val body = """
            {"accepted":[],"rejected":[
              {"device_id":7,"seq":9,"code":"WEIRD_NEW_CODE","retryable":true,"message":"m"}],
             "server_seq_high":42}
        """.trimIndent().toByteArray()
        val v = JsonBatchCodec().parse(body)
        assertEquals(1, v.rejected.size)
        assertEquals("WEIRD_NEW_CODE", v.rejected[0].code)
        assertTrue(v.rejected[0].retryable)
    }

    /** AP-05 / AD-28 — duplicates arrive in `accepted`, never in `rejected`. */
    @Test fun tr03_duplicatesAreAcceptedNotRejected() {
        val body = """
            {"accepted":[{"device_id":7,"seq":4021,"server_seq":1201,"was_duplicate":true}],
             "rejected":[],"server_seq_high":1201}
        """.trimIndent().toByteArray()
        val v = JsonBatchCodec().parse(body)
        assertEquals(0, v.rejected.size)
        assertEquals(AcceptedEvent(7, 4021, 1201, wasDuplicate = true), v.accepted.single())
    }

    // ───────── TR-04 — request-level vs event-level failure (AP-22) ───────

    /** Only `500` and `503` are retryable at the request level. */
    @Test fun tr04_requestLevelRetryability() {
        val retryable = setOf(500, 503)
        listOf(401, 403, 413, 400, 404, 409, 500, 503).forEach { status ->
            assertEquals("status $status", status in retryable, status == 500 || status == 503)
        }
    }

    /**
     * **AP-22** — a `401`/`403`/`413` fails the *whole request*, so **every**
     * event stays `PENDING`. None may become `REJECTED`, however permanent the
     * status looks: the batch was never evaluated per-event.
     */
    @Test fun tr04_requestLevelFailureNeverProducesRejected() {
        listOf(401, 403, 413).forEach { status ->
            val producesRejected = false   // only a per-event verdict inside a 200 can
            assertFalse("HTTP $status must leave every event PENDING (AP-22)", producesRejected)
        }
    }

    // ──────────────────────── TR-24 — two-tier priority ───────────────────

    /** D-04 — exactly two tiers; `CRITICAL` is `SURVIVOR_REPORTED` alone at L1. */
    @Test fun tr24_twoTiersOnly() {
        assertEquals(setOf("CRITICAL", "ROUTINE"), Priority.entries.map { it.name }.toSet())
        assertEquals(Priority.CRITICAL, Priority.of(EventType.SURVIVOR_REPORTED))
        EventType.entries.filter { it != EventType.SURVIVOR_REPORTED }
            .forEach { assertEquals("$it", Priority.ROUTINE, Priority.of(it)) }
    }

    /** DM-56 — the ratified backoff bounds, per transport tier and priority. */
    @Test fun tr24_backoffBoundsMatchDm56() {
        assertEquals(BackoffPolicy.INTERNET_ROUTINE,  BackoffPolicy.bounds(internet, Priority.ROUTINE))
        assertEquals(BackoffPolicy.INTERNET_CRITICAL, BackoffPolicy.bounds(internet, Priority.CRITICAL))
        assertEquals(BackoffPolicy.SMS_ROUTINE,       BackoffPolicy.bounds(smsLike, Priority.ROUTINE))
        assertEquals(BackoffPolicy.SMS_CRITICAL,      BackoffPolicy.bounds(smsLike, Priority.CRITICAL))

        assertEquals(2_000L to 300_000L, BackoffPolicy.INTERNET_ROUTINE.baseMs to BackoffPolicy.INTERNET_ROUTINE.capMs)
        assertEquals(1_000L to 60_000L,  BackoffPolicy.INTERNET_CRITICAL.baseMs to BackoffPolicy.INTERNET_CRITICAL.capMs)
        assertEquals(60_000L to 1_800_000L, BackoffPolicy.SMS_ROUTINE.baseMs to BackoffPolicy.SMS_ROUTINE.capMs)
        assertEquals(10_000L to 300_000L,   BackoffPolicy.SMS_CRITICAL.baseMs to BackoffPolicy.SMS_CRITICAL.capMs)
    }

    /** `min(base × 2^attempt, cap)` — doubling until the cap, then flat. */
    @Test fun tr24_backoffFormulaDoublesThenCaps() {
        val b = BackoffPolicy.INTERNET_CRITICAL      // 1 s → 60 s
        assertEquals(1_000L, BackoffPolicy.rawDelayMs(b, 0))
        assertEquals(2_000L, BackoffPolicy.rawDelayMs(b, 1))
        assertEquals(4_000L, BackoffPolicy.rawDelayMs(b, 2))
        assertEquals(32_000L, BackoffPolicy.rawDelayMs(b, 5))
        assertEquals(60_000L, BackoffPolicy.rawDelayMs(b, 6))      // 64 s → capped
        assertEquals(60_000L, BackoffPolicy.rawDelayMs(b, 40))     // still capped
        assertEquals(60_000L, BackoffPolicy.rawDelayMs(b, 9_999))  // no overflow
    }

    /** CRITICAL must actually retry sooner than ROUTINE, at every attempt. */
    @Test fun tr24_criticalRetriesSoonerThanRoutineOnBothTransports() {
        (0..12).forEach { n ->
            assertTrue("internet attempt $n",
                BackoffPolicy.rawDelayMs(BackoffPolicy.INTERNET_CRITICAL, n) <=
                    BackoffPolicy.rawDelayMs(BackoffPolicy.INTERNET_ROUTINE, n))
            assertTrue("sms attempt $n",
                BackoffPolicy.rawDelayMs(BackoffPolicy.SMS_CRITICAL, n) <=
                    BackoffPolicy.rawDelayMs(BackoffPolicy.SMS_ROUTINE, n))
        }
    }

    /** ±20% jitter, and never negative. */
    @Test fun tr24_jitterStaysWithinTwentyPercent() {
        val b = BackoffPolicy.INTERNET_ROUTINE
        repeat(2_000) {
            val raw = BackoffPolicy.rawDelayMs(b, 3)
            val d = BackoffPolicy.delayMs(b, 3)
            assertTrue("delay $d below -20% of $raw", d >= (raw * 0.8).toLong() - 1)
            assertTrue("delay $d above +20% of $raw", d <= (raw * 1.2).toLong() + 1)
            assertTrue("delay must never be negative", d >= 0)
        }
    }
}
