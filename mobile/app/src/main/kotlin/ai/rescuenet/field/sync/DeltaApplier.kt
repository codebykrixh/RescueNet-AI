package ai.rescuenet.field.sync

import androidx.room.withTransaction
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.SyncState

/**
 * Delta application and watermark advancement — **`08` §12.3 / DM-55**, M7.
 *
 * DM-55's binding requirement: *"The watermark advance MUST occur in the same
 * Room transaction that applies the delta events. Either the events and the new
 * watermark both commit, or neither does."*
 *
 * [applyPage] is the **only** way the watermark moves. `SyncStateDao` opens no
 * transaction of its own precisely so that an advance outside a delta
 * transaction is awkward to write by accident.
 *
 * Why the pairing is load-bearing, in both directions:
 *
 * | Advance *before* the events commit | Advance *after* |
 * |---|---|
 * | A crash in between loses those events **permanently** — the next pull starts past them and never asks again | A crash in between re-pulls events already held. Dedup absorbs it, but the marker no longer describes the log, and on a metered link the wasted pull is not free |
 *
 * Pairing them removes both. This is **AD-12** made enforceable rather than
 * merely intended: `06` §5.4's *"a crash mid-way resumes with identical result"*
 * is true only under this pairing.
 *
 * Deduplication is `(device_id, seq)` and nothing else (**DM-06**), applied by
 * `INSERT … ON CONFLICT IGNORE`, so replaying an identical page is a no-op
 * rather than an overwrite.
 */
class DeltaApplier(private val db: FieldDatabase) {

    /** Current watermark; `0` (=[SyncState.UNSYNCED]) if nothing has been applied. */
    suspend fun watermark(): Long = db.syncState().peek() ?: SyncState.UNSYNCED

    /** Seeds the singleton row. Safe to call repeatedly. */
    suspend fun ensureInitialised() = db.syncState().initialise()

    /**
     * Applies one delta page **atomically with the watermark advance**.
     *
     * @param events   the page, canonical per `08` Part 1, ascending by `server_seq`.
     * @param nextSince the server's `next_since` for this page (`09` §3.4). The
     *   client advances **only after successfully applying the page** — which
     *   here means: in the same commit.
     * @return how many events were newly inserted (duplicates excluded).
     * @throws IllegalArgumentException if an event carries no `server_seq`; a
     *   delta event without one cannot be positioned in the downlink order, and
     *   silently applying it would let the watermark outrun the log.
     */
    suspend fun applyPage(events: List<LocalEvent>, nextSince: Long): Int =
        db.withTransaction {
            require(events.all { it.serverSeq != null }) {
                "delta events must carry server_seq (08 §1.3 column B)"
            }
            db.syncState().initialise()
            val rowIds = db.events().insertReceived(events)
            val inserted = rowIds.count { it != -1L }
            db.syncState().advanceTo(nextSince)
            inserted
        }

    /**
     * `09` §3.6 — if the device is more than [SNAPSHOT_THRESHOLD] events behind,
     * a snapshot is cheaper than paging. This reports the decision; taking the
     * snapshot is a read-model concern, not M7's.
     */
    fun shouldSnapshot(currentServerSeq: Long, lastApplied: Long): Boolean =
        currentServerSeq - lastApplied > SNAPSHOT_THRESHOLD

    companion object {
        /** `09` §3.6: "If `current_server_seq − last_applied > 2000`, re-snapshot". */
        const val SNAPSHOT_THRESHOLD = 2000L
    }
}
