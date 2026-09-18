package ai.rescuenet.field.store

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface EventDao {

    /**
     * Append-only insert. `IGNORE` gives the same idempotency the server has:
     * a second arrival of the same `(device_id, seq)` is a no-op, never an
     * overwrite (`08` Part 5, DM-06).
     */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(event: LocalEvent): Long

    @Query("SELECT * FROM event WHERE device_id = :deviceId AND seq = :seq")
    suspend fun find(deviceId: Int, seq: Long): LocalEvent?

    @Query("SELECT COUNT(*) FROM event")
    suspend fun count(): Int

    @Query("SELECT * FROM event ORDER BY device_id, seq")
    suspend fun all(): List<LocalEvent>

    @Query("SELECT seq FROM event WHERE device_id = :deviceId ORDER BY seq")
    suspend fun seqsFor(deviceId: Int): List<Long>

    /**
     * Applies one delta event. `IGNORE` is the dedup rule of `08` Part 5 and
     * DM-06 — `(device_id, seq)` and nothing else. A redelivered event is a
     * no-op, never an overwrite, so replaying a page is safe. **M7.**
     */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertReceived(events: List<LocalEvent>): List<Long>

    @Query("SELECT MAX(server_seq) FROM event WHERE server_seq IS NOT NULL")
    suspend fun highestAppliedServerSeq(): Long?

    /**
     * The incident's declaring event, if the device has received it.
     *
     * `INCIDENT_DECLARED` is server-authored and reaches the device through the
     * ordinary delta pull (`06` §5.4), so it is already in this log — no extra
     * table and no extra fetch. **M8** reads its `started_at` to anchor the SMS
     * batch header's `base_t` (`09` §6.6.1), which is why this query exists.
     */
    @Query(
        "SELECT * FROM event WHERE incident_id = :incidentId AND type = :typeCode " +
            "ORDER BY seq LIMIT 1"
    )
    suspend fun findIncidentDeclared(incidentId: Int, typeCode: Int): LocalEvent?
}

@Dao
interface OutboxDao {

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(row: OutboxRow): Long

    @Query("SELECT * FROM outbox WHERE device_id = :deviceId AND seq = :seq")
    suspend fun find(deviceId: Int, seq: Long): OutboxRow?

    @Query("SELECT COUNT(*) FROM outbox")
    suspend fun count(): Int

    @Query("SELECT COUNT(*) FROM outbox WHERE state = :state")
    suspend fun countInState(state: OutboxState): Int

    @Query("SELECT * FROM outbox ORDER BY device_id, seq")
    suspend fun all(): List<OutboxRow>

    /**
     * Retention pruning — `08` §6.3, FR-811, **DM-18** and **DM-40**.
     *
     * The `WHERE` clause is the guarantee, not a convention: only `ACKED` rows
     * can ever match, so `PENDING`, `IN_FLIGHT` and `REJECTED` rows are
     * structurally unreachable by this statement. `REJECTED` rows are never
     * pruned because the rejection reason must survive for diagnosis (DM-40).
     *
     * *When* to prune is a storage-pressure policy question and is not M6's.
     * This is the representation-level guard only.
     */
    @Query("DELETE FROM outbox WHERE state = 'ACKED'")
    suspend fun pruneAckedRows(): Int

    // ---------------------------------------------------------------- M7 ----
    // Transition behaviour. The columns these touch are all M6's (`08` §6.1);
    // M7 adds no column and changes no shape (`12` §3.4).

    /**
     * Selects the next batch to send: `PENDING` rows whose backoff has elapsed,
     * **CRITICAL first** (`06` §5.3 — "Drain and pack CRITICAL first, always"),
     * then oldest-queued within a tier so nothing starves.
     *
     * `REJECTED` rows are not `PENDING`, so they are skipped forever and consume
     * no transmission capacity (`09` §2.7.3).
     */
    @Query(
        "SELECT * FROM outbox WHERE state = 'PENDING' " +
            "AND (next_attempt_at IS NULL OR next_attempt_at <= :now) " +
            "ORDER BY CASE priority WHEN 'CRITICAL' THEN 0 ELSE 1 END, first_queued_at, seq " +
            "LIMIT :limit"
    )
    suspend fun nextSendable(now: Long, limit: Int): List<OutboxRow>

    /** `PENDING → IN_FLIGHT`: packed into a batch and handed to a transport. */
    @Query(
        "UPDATE outbox SET state = 'IN_FLIGHT', batch_ref = :batchRef " +
            "WHERE state = 'PENDING' AND device_id = :deviceId AND seq = :seq"
    )
    suspend fun markInFlight(deviceId: Int, seq: Long, batchRef: Long): Int

    /** `IN_FLIGHT → ACKED`: the server confirmed the event is persisted. */
    @Query(
        "UPDATE outbox SET state = 'ACKED', last_error = NULL " +
            "WHERE state = 'IN_FLIGHT' AND device_id = :deviceId AND seq = :seq"
    )
    suspend fun markAcked(deviceId: Int, seq: Long): Int

    /**
     * `IN_FLIGHT → PENDING`: transport failure, timeout, or a **retryable**
     * rejection. `attempt_count` increments and `next_attempt_at` is persisted
     * so backoff survives restart (`08` §6.1, §6.3).
     */
    @Query(
        "UPDATE outbox SET state = 'PENDING', attempt_count = attempt_count + 1, " +
            "next_attempt_at = :nextAttemptAt, last_error = :error, batch_ref = NULL " +
            "WHERE state = 'IN_FLIGHT' AND device_id = :deviceId AND seq = :seq"
    )
    suspend fun returnToPending(deviceId: Int, seq: Long, nextAttemptAt: Long, error: String?): Int

    /**
     * `IN_FLIGHT → REJECTED`: **only** on a `200` response listing the event
     * with `retryable: false` (`09` §2.7.1, AP-14). Terminal delivery state —
     * the row is never pruned (DM-40) and the event is never deleted (DM-39).
     */
    @Query(
        "UPDATE outbox SET state = 'REJECTED', batch_ref = NULL, " +
            "rejected_code = :code, rejected_message = :message, " +
            "rejected_at = :at, rejected_batch_ref = :batchRef " +
            "WHERE state = 'IN_FLIGHT' AND device_id = :deviceId AND seq = :seq"
    )
    suspend fun markRejected(
        deviceId: Int, seq: Long, code: String, message: String?, at: Long, batchRef: String?,
    ): Int

    /**
     * Restart recovery — `08` §6.3 "After restart": every `IN_FLIGHT` row
     * reverts to `PENDING`. Re-sending is always safe (`08` §6.2 note), because
     * `(device_id, seq)` makes redelivery a server-side no-op.
     *
     * `attempt_count` and `next_attempt_at` are **left exactly as persisted** —
     * "Backoff resumes from persisted `next_attempt_at`. Nothing is re-derived
     * from memory." A crash is not a delivery attempt, so it does not consume
     * one.
     */
    @Query("UPDATE outbox SET state = 'PENDING', batch_ref = NULL WHERE state = 'IN_FLIGHT'")
    suspend fun reclaimInFlight(): Int

    @Query("SELECT * FROM outbox WHERE state = 'REJECTED' ORDER BY rejected_at DESC")
    suspend fun rejectedRows(): List<OutboxRow>
}

@Dao
interface SeqCounterDao {

    @Query("SELECT next_seq FROM seq_counter WHERE device_id = :deviceId")
    suspend fun peek(deviceId: Int): Long?

    @Query("INSERT OR IGNORE INTO seq_counter (device_id, next_seq) VALUES (:deviceId, :start)")
    suspend fun initialise(deviceId: Int, start: Long)

    @Query("UPDATE seq_counter SET next_seq = next_seq + 1 WHERE device_id = :deviceId")
    suspend fun advance(deviceId: Int)
}
