package ai.rescuenet.field.store

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index

/**
 * Persisted outbox delivery state — **`08` §6.1**.
 *
 * `08` §6.1 lists twelve rows; the first names the composite key
 * `device_id, seq`, so the table has **13 physical columns**. All twelve
 * documented entries are present, including the four AP-14 rejection columns.
 *
 * **None of these is part of the canonical event** (Part 1), none is ever
 * transmitted, and none appears in the `event` table. **DM-39.**
 *
 * M6 owns this *representation*. The transition engine that moves rows between
 * states — retry, backoff, priority drain, transport, ACK/REJECT processing and
 * `IN_FLIGHT` → `PENDING` restart recovery — is **M7** (`12` §3.4).
 */
@Entity(
    tableName = "outbox",
    primaryKeys = ["device_id", "seq"],
    foreignKeys = [
        ForeignKey(
            entity = LocalEvent::class,
            parentColumns = ["device_id", "seq"],
            childColumns = ["device_id", "seq"],
            onDelete = ForeignKey.RESTRICT,
        ),
    ],
    indices = [Index(value = ["state", "priority"])],
)
data class OutboxRow(
    @ColumnInfo(name = "device_id") val deviceId: Int,
    @ColumnInfo(name = "seq") val seq: Long,

    /** `PENDING` · `IN_FLIGHT` · `ACKED` · `REJECTED` — `08` §6.2. */
    @ColumnInfo(name = "state") val state: OutboxState,

    /** Derived from the event type at insert (DM-02). */
    @ColumnInfo(name = "priority") val priority: String,

    /** Drives backoff. The backoff *policy* is M7. */
    @ColumnInfo(name = "attempt_count") val attemptCount: Int = 0,

    /** Persisted so backoff survives restart (`08` §6.1). Set by M7. */
    @ColumnInfo(name = "next_attempt_at") val nextAttemptAt: Long? = null,

    /** Diagnostics only. */
    @ColumnInfo(name = "last_error") val lastError: String? = null,

    /** Which in-flight batch carries it. Set by M7. */
    @ColumnInfo(name = "batch_ref") val batchRef: Long? = null,

    /** Feeds the "unsent for N hours" diagnostic. */
    @ColumnInfo(name = "first_queued_at") val firstQueuedAt: Long,

    // ---- the four AP-14 rejection columns — delivery metadata only (DM-39)
    @ColumnInfo(name = "rejected_code") val rejectedCode: String? = null,
    @ColumnInfo(name = "rejected_message") val rejectedMessage: String? = null,
    @ColumnInfo(name = "rejected_at") val rejectedAt: Long? = null,
    @ColumnInfo(name = "rejected_batch_ref") val rejectedBatchRef: String? = null,
)

/**
 * The four persisted outbox states — `08` §6.2.
 *
 * There is deliberately **no `RETRY`** state: retry is `PENDING` with a future
 * `next_attempt_at` (DM-16). There is deliberately **no `PRUNED`** state:
 * pruning is row deletion under the retention policy, so a pruned row holds no
 * state (`06` §5.3 terminology note).
 *
 * `REJECTED` is a terminal **delivery** state describing the outbox row, never
 * the event. The domain event stays permanently in the local log and is never
 * deleted because it was rejected (DM-39, DM-40).
 */
enum class OutboxState { PENDING, IN_FLIGHT, ACKED, REJECTED }
