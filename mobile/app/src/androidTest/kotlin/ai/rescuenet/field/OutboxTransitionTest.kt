package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEventStore
import ai.rescuenet.field.store.OutboxState
import ai.rescuenet.field.sync.AcceptedEvent
import ai.rescuenet.field.sync.BatchVerdict
import ai.rescuenet.field.sync.OutboxEngine
import ai.rescuenet.field.sync.RejectedEvent
import ai.rescuenet.field.transport.CostClass
import ai.rescuenet.field.transport.LatencyClass
import ai.rescuenet.field.transport.SendOutcome
import ai.rescuenet.field.transport.TransportCapabilities
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The M7 outbox transition engine against a real database — the four ratified
 * transitions of `08` §6.2 and nothing else.
 */
@RunWith(AndroidJUnit4::class)
class OutboxTransitionTest {

    private lateinit var db: FieldDatabase
    private lateinit var store: LocalEventStore
    private lateinit var engine: OutboxEngine

    private val internet = TransportCapabilities(
        256 * 1024, true, LatencyClass.FAST, CostClass.FREE, true, true)

    @Before fun setUp() {
        db = inMemoryDb(); store = LocalEventStore(db); engine = OutboxEngine(db)
    }
    @After fun tearDown() = db.close()

    private suspend fun queueRoutine(n: Int) = (1..n).map { store.appendCellStatus(entityId = it.toLong()) }
    private suspend fun queueCritical(n: Int) = (1..n).map { store.appendSurvivor(entityId = it.toLong()) }
    private suspend fun state(seq: Long) = db.outbox().find(DEVICE_ID, seq)!!.state

    // ────────────────────────── PENDING → IN_FLIGHT ───────────────────────

    @Test fun pendingBecomesInFlightWhenBatched() = runTest {
        val seqs = queueRoutine(3)
        val rows = engine.nextBatch(now = Long.MAX_VALUE, limit = 10)
        assertEquals(3, rows.size)
        assertEquals(3, engine.markBatchInFlight(rows, batchRef = 77L))
        seqs.forEach { assertEquals(OutboxState.IN_FLIGHT, state(it)) }
        assertEquals(77L, db.outbox().find(DEVICE_ID, seqs[0])!!.batchRef)
    }

    // ──────────────────────────── IN_FLIGHT → ACKED ───────────────────────

    @Test fun acceptedEventsBecomeAcked() = runTest {
        val seqs = queueRoutine(2)
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        val verdict = BatchVerdict(
            accepted = seqs.map { AcceptedEvent(DEVICE_ID, it, 1000 + it, wasDuplicate = false) },
            rejected = emptyList(), serverSeqHigh = 1002,
        )
        val r = engine.applyVerdict(verdict, emptyMap(), internet, "b1", now = 1L)
        assertEquals(2, r.acked)
        seqs.forEach { assertEquals(OutboxState.ACKED, state(it)) }
    }

    /** AP-05 / AD-28 — a duplicate is *accepted*, so the client still ACKs it. */
    @Test fun duplicateAcceptanceStillAcks() = runTest {
        val seq = queueRoutine(1).single()
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        val v = BatchVerdict(listOf(AcceptedEvent(DEVICE_ID, seq, 500, wasDuplicate = true)), emptyList(), 500)
        assertEquals(1, engine.applyVerdict(v, emptyMap(), internet, "b", 1L).acked)
        assertEquals(OutboxState.ACKED, state(seq))
    }

    // ─────────────────── IN_FLIGHT → PENDING (retryable) ──────────────────

    @Test fun retryableRejectionReturnsToPendingWithPersistedBackoff() = runTest {
        val seq = queueRoutine(1).single()
        val rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)
        val byKey = rows.associateBy { it.deviceId to it.seq }
        val v = BatchVerdict(emptyList(),
            listOf(RejectedEvent(DEVICE_ID, seq, "UNAVAILABLE", retryable = true, message = "db down")), null)

        val r = engine.applyVerdict(v, byKey, internet, "b", now = 10_000L)

        assertEquals(1, r.returnedToPending)
        assertEquals(0, r.rejected)
        val row = db.outbox().find(DEVICE_ID, seq)!!
        assertEquals(OutboxState.PENDING, row.state)
        assertEquals("attempt_count must increment", 1, row.attemptCount)
        assertNotNull("next_attempt_at must be persisted (08 §6.1)", row.nextAttemptAt)
        assertTrue("backoff must be in the future", row.nextAttemptAt!! > 10_000L)
    }

    // ────────────────── IN_FLIGHT → REJECTED (permanent) ──────────────────

    /** `09` §2.7.1 / AP-14 — entry requires `retryable: false`. */
    @Test fun permanentRejectionRecordsAllFourColumns() = runTest {
        val seq = queueRoutine(1).single()
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        val v = BatchVerdict(emptyList(),
            listOf(RejectedEvent(DEVICE_ID, seq, "UNKNOWN_CELL", retryable = false, message = "cell 9999 not in grid")), null)

        assertEquals(1, engine.applyVerdict(v, emptyMap(), internet, "batch-xyz", now = 555L).rejected)

        val row = db.outbox().find(DEVICE_ID, seq)!!
        assertEquals(OutboxState.REJECTED, row.state)
        assertEquals("UNKNOWN_CELL", row.rejectedCode)
        assertEquals("cell 9999 not in grid", row.rejectedMessage)
        assertEquals(555L, row.rejectedAt)
        assertEquals("batch-xyz", row.rejectedBatchRef)
        assertNotNull("DM-39: the event is never deleted", db.events().find(DEVICE_ID, seq))
    }

    /**
     * **AP-21, at the database level.** An unknown code with `retryable: true`
     * must go to `PENDING`; the same unknown code with `retryable: false` must
     * go to `REJECTED`. A code-parsing implementation cannot pass both.
     */
    @Test fun unknownCodeIsRoutedPurelyByTheBoolean() = runTest {
        val a = queueRoutine(1).single()
        val b = store.appendCellStatus(entityId = 42)
        val rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)
        val v = BatchVerdict(emptyList(), listOf(
            RejectedEvent(DEVICE_ID, a, "CODE_FROM_THE_FUTURE", retryable = true, message = null),
            RejectedEvent(DEVICE_ID, b, "CODE_FROM_THE_FUTURE", retryable = false, message = null),
        ), null)

        engine.applyVerdict(v, rows.associateBy { it.deviceId to it.seq }, internet, "b", 1L)

        assertEquals(OutboxState.PENDING, state(a))
        assertEquals(OutboxState.REJECTED, state(b))
    }

    /** `09` §2.7.3 — a REJECTED row is not PENDING, so it never blocks the queue again. */
    @Test fun rejectedRowsAreNeverSelectedAgain() = runTest {
        val seq = queueRoutine(1).single()
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        engine.applyVerdict(
            BatchVerdict(emptyList(), listOf(RejectedEvent(DEVICE_ID, seq, "X", false, null)), null),
            emptyMap(), internet, "b", 1L)
        assertEquals("a REJECTED row must never be batched again",
            0, engine.nextBatch(Long.MAX_VALUE, 10).size)
    }

    // ───────────────────────── AP-22 request-level ────────────────────────

    /**
     * **AP-22** — a `401`/`403`/`413` fails the whole request. Every event
     * returns to `PENDING`; **none** becomes `REJECTED`, however permanent the
     * status looks.
     */
    @Test fun requestLevelFailureLeavesEveryEventPendingAndNoneRejected() = runTest {
        val seqs = queueRoutine(3)
        val rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)

        listOf(401, 403, 413).forEach { status ->
            val inFlight = db.outbox().all().filter { it.state == OutboxState.PENDING }
            engine.applyRequestFailure(
                rows, SendOutcome.RequestFailed(status, retryableAtRequestLevel = false, detail = "denied"),
                internet, now = 1_000L)
            engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        }
        engine.applyRequestFailure(
            rows, SendOutcome.RequestFailed(401, false, "denied"), internet, 1_000L)

        assertEquals("no row may be REJECTED by a request-level failure (AP-22)",
            0, db.outbox().countInState(OutboxState.REJECTED))
        seqs.forEach { assertEquals(OutboxState.PENDING, state(it)) }
    }

    @Test fun transportFailureReturnsEverythingToPending() = runTest {
        val seqs = queueRoutine(2)
        val rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)
        val n = engine.applyRequestFailure(
            rows, SendOutcome.RequestFailed(null, retryableAtRequestLevel = true, detail = "timeout"),
            internet, now = 2_000L)
        assertEquals(2, n)
        seqs.forEach { assertEquals(OutboxState.PENDING, state(it)) }
        assertEquals(0, db.outbox().countInState(OutboxState.REJECTED))
    }

    // ─────────────────────── priority drain (TR-24) ───────────────────────

    /** `06` §5.3 — "Drain and pack CRITICAL first, always." */
    @Test fun criticalIsDrainedBeforeRoutine() = runTest {
        queueRoutine(5)                       // queued first
        val critical = queueCritical(2)       // queued later
        val batch = engine.nextBatch(Long.MAX_VALUE, limit = 3)
        assertEquals(3, batch.size)
        assertEquals("CRITICAL must head the batch despite being queued later",
            listOf(Priority.CRITICAL.name, Priority.CRITICAL.name, Priority.ROUTINE.name),
            batch.map { it.priority })
        assertEquals(critical.toSet(), batch.take(2).map { it.seq }.toSet())
    }

    /** Backoff is respected: a row whose next_attempt_at is in the future is not selected. */
    @Test fun backoffDefersSelectionUntilNextAttemptAt() = runTest {
        val seq = queueRoutine(1).single()
        val rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)
        engine.applyRequestFailure(rows, SendOutcome.RequestFailed(500, true, "boom"), internet, now = 100_000L)

        val next = db.outbox().find(DEVICE_ID, seq)!!.nextAttemptAt!!
        assertEquals("not yet due", 0, engine.nextBatch(now = next - 1, limit = 10).size)
        assertEquals("due", 1, engine.nextBatch(now = next, limit = 10).size)
    }

    // ───────────────────────── restart recovery ───────────────────────────

    /**
     * `08` §6.3 "After restart" — `IN_FLIGHT` → `PENDING`, and **persisted
     * retry state is preserved**: *"Backoff resumes from persisted
     * `next_attempt_at`. Nothing is re-derived from memory."*
     *
     * A crash is not a delivery attempt, so it must not consume one.
     */
    @Test fun restartReclaimsInFlightWithoutTouchingRetryState() = runTest {
        val seq = queueRoutine(1).single()
        var rows = engine.nextBatch(Long.MAX_VALUE, 10)
        engine.markBatchInFlight(rows, 1L)
        engine.applyRequestFailure(rows, SendOutcome.RequestFailed(503, true, "unavailable"), internet, 50_000L)

        val afterFailure = db.outbox().find(DEVICE_ID, seq)!!
        rows = engine.nextBatch(afterFailure.nextAttemptAt!!, 10)
        engine.markBatchInFlight(rows, 2L)
        assertEquals(OutboxState.IN_FLIGHT, state(seq))

        // ---- process dies here; next start calls recoverAfterRestart()
        assertEquals(1, engine.recoverAfterRestart())

        val recovered = db.outbox().find(DEVICE_ID, seq)!!
        assertEquals(OutboxState.PENDING, recovered.state)
        assertEquals("attempt_count must NOT be incremented by a restart",
            afterFailure.attemptCount, recovered.attemptCount)
        assertEquals("next_attempt_at must survive verbatim",
            afterFailure.nextAttemptAt, recovered.nextAttemptAt)
        assertNull("batch_ref must be cleared", recovered.batchRef)
    }

    /** Restart must not disturb ACKED or REJECTED rows. */
    @Test fun restartLeavesSettledRowsAlone() = runTest {
        val acked = queueRoutine(1).single()
        val rejected = store.appendCellStatus(entityId = 900)
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        engine.applyVerdict(
            BatchVerdict(
                listOf(AcceptedEvent(DEVICE_ID, acked, 1, false)),
                listOf(RejectedEvent(DEVICE_ID, rejected, "X", false, null)), null),
            emptyMap(), internet, "b", 1L)

        assertEquals(0, engine.recoverAfterRestart())
        assertEquals(OutboxState.ACKED, state(acked))
        assertEquals(OutboxState.REJECTED, state(rejected))
    }

    /** Only the four ratified transitions exist — no path leaves ACKED or REJECTED. */
    @Test fun thereIsNoExitFromRejected() = runTest {
        val seq = queueRoutine(1).single()
        engine.markBatchInFlight(engine.nextBatch(Long.MAX_VALUE, 10), 1L)
        engine.applyVerdict(
            BatchVerdict(emptyList(), listOf(RejectedEvent(DEVICE_ID, seq, "X", false, null)), null),
            emptyMap(), internet, "b", 1L)

        // Every engine entry point, applied again: none may move it (09 §2.7.5).
        engine.recoverAfterRestart()
        engine.applyVerdict(
            BatchVerdict(listOf(AcceptedEvent(DEVICE_ID, seq, 9, false)), emptyList(), null),
            emptyMap(), internet, "b", 2L)
        assertEquals(OutboxState.REJECTED, state(seq))
    }
}
