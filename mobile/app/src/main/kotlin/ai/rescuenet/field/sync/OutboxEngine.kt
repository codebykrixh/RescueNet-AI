package ai.rescuenet.field.sync

import androidx.room.withTransaction
import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.OutboxRow
import ai.rescuenet.field.transport.SendOutcome
import ai.rescuenet.field.transport.TransportCapabilities
import kotlin.random.Random

/**
 * The outbox **transition engine** — M7 (`12` §3.4).
 *
 * M6 owns the outbox's shape; this owns its movement. Only the four ratified
 * transitions of `08` §6.2 exist here, and no other class may write
 * `outbox.state`:
 *
 * ```
 * PENDING   → IN_FLIGHT   packed into a batch and handed to a transport
 * IN_FLIGHT → ACKED       server confirms persisted
 * IN_FLIGHT → PENDING     transport failure, timeout, or retryable rejection
 * IN_FLIGHT → REJECTED    server returns a PERMANENT verdict (retryable: false)
 * ```
 *
 * There is no `RETRY` state (DM-16) and no `PRUNED` state — pruning is row
 * deletion, so a pruned row holds no state (`06` §5.3).
 */
class OutboxEngine(
    private val db: FieldDatabase,
    private val random: Random = Random.Default,
) {

    /**
     * Restart recovery — `08` §6.3 "After restart", and M7's stated completion
     * criterion.
     *
     * Every `IN_FLIGHT` row reverts to `PENDING`. Re-sending is always safe:
     * `(device_id, seq)` is unchanged, so the server de-duplicates (`08` Part 5).
     *
     * **`attempt_count` and `next_attempt_at` are left exactly as persisted.**
     * *"Backoff resumes from persisted `next_attempt_at`. Nothing is re-derived
     * from memory."* A crash is not a delivery attempt and must not consume one,
     * or a device that crash-loops would back itself off to the cap without ever
     * having reached the network.
     *
     * @return how many rows were reclaimed.
     */
    suspend fun recoverAfterRestart(): Int = db.outbox().reclaimInFlight()

    /**
     * Selects the next sendable rows: `PENDING`, backoff elapsed, **CRITICAL
     * first** (`06` §5.3), oldest-first within a tier.
     */
    suspend fun nextBatch(now: Long, limit: Int): List<OutboxRow> =
        db.outbox().nextSendable(now, limit)

    /** `PENDING → IN_FLIGHT` for a whole batch, atomically. */
    suspend fun markBatchInFlight(rows: List<OutboxRow>, batchRef: Long): Int =
        db.withTransaction {
            rows.count { db.outbox().markInFlight(it.deviceId, it.seq, batchRef) > 0 }
        }

    /**
     * Applies a **request-level** outcome — **AP-22**.
     *
     * A `401`, `403` or `413` fails the *whole request*: the batch was never
     * evaluated per-event, so **every** event returns to `PENDING`. **No event
     * may become `REJECTED` on this path**, however permanent the status looks.
     * Only a per-event verdict inside a `200` can do that (`09` §2.7.1).
     *
     * A non-retryable request failure still returns rows to `PENDING`; it
     * differs only in that retrying will not help until the cause is fixed
     * (a re-enrolment, a smaller batch). Holding the events is the contract's
     * choice: *"Never drops an event"* (`06` §5.3).
     */
    suspend fun applyRequestFailure(
        rows: List<OutboxRow>,
        outcome: SendOutcome.RequestFailed,
        capabilities: TransportCapabilities,
        now: Long,
    ): Int = db.withTransaction {
        rows.count { row ->
            val next = BackoffPolicy.nextAttemptAt(
                now, capabilities, Priority.valueOf(row.priority), row.attemptCount, random,
            )
            val detail = "request-level ${outcome.httpStatus ?: "transport"}: ${outcome.detail ?: "no detail"}"
            db.outbox().returnToPending(row.deviceId, row.seq, next, detail) > 0
        }
    }

    /**
     * Applies a per-event [BatchVerdict] from a `200` response.
     *
     * * `accepted` → `ACKED`, **including duplicates** (`was_duplicate: true`
     *   still means the server holds it — AP-05).
     * * `rejected` with **`retryable == true`** → back to `PENDING` with
     *   backoff.
     * * `rejected` with **`retryable == false`** → `REJECTED`, recording all
     *   four AP-14 columns.
     *
     * **AP-21 is enforced structurally**: the only field consulted for the
     * branch is [RejectedEvent.retryable]. `code` is stored verbatim and never
     * compared against anything — there is no `when (code)` in this file, and a
     * test asserts an unknown code behaves purely by its boolean.
     *
     * Rows named by the server but not currently `IN_FLIGHT` are ignored: the
     * DAO's `WHERE state = 'IN_FLIGHT'` makes every transition a no-op unless
     * the row is genuinely in flight, so a duplicated or late response cannot
     * resurrect a settled row.
     *
     * Events the server did not mention stay `PENDING` — *"Unmentioned events
     * stay PENDING"* (`06` §5.3) — which the caller achieves by leaving them
     * untouched here and reclaiming them on restart or timeout.
     */
    suspend fun applyVerdict(
        verdict: BatchVerdict,
        rowsByKey: Map<Pair<Int, Long>, OutboxRow>,
        capabilities: TransportCapabilities,
        batchId: String?,
        now: Long,
    ): VerdictResult = db.withTransaction {
        var acked = 0; var requeued = 0; var rejected = 0

        verdict.accepted.forEach { a ->
            if (db.outbox().markAcked(a.deviceId, a.seq) > 0) acked++
        }

        verdict.rejected.forEach { r ->
            if (r.retryable) {
                val row = rowsByKey[r.deviceId to r.seq]
                val attempt = row?.attemptCount ?: 0
                val priority = row?.priority?.let(Priority::valueOf) ?: Priority.ROUTINE
                val next = BackoffPolicy.nextAttemptAt(now, capabilities, priority, attempt, random)
                if (db.outbox().returnToPending(r.deviceId, r.seq, next, "retryable: ${r.code}") > 0) requeued++
            } else {
                if (db.outbox().markRejected(
                        r.deviceId, r.seq, r.code, r.message, now, batchId,
                    ) > 0
                ) rejected++
            }
        }
        VerdictResult(acked, requeued, rejected)
    }

    data class VerdictResult(val acked: Int, val returnedToPending: Int, val rejected: Int)
}
