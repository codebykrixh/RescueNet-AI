package ai.rescuenet.field.store

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Device-side synchronisation state — **`08` §12.3, DM-55**.
 *
 * Holds the **downlink watermark** `last_applied_server_seq`: everything after
 * it is owed to the device (`06` §5.4). `09` §3.3 fixes what it is — **it *is* a
 * `server_seq`**, a plain integer, never an opaque cursor and never a device
 * `seq`.
 *
 * DM-55 requires this to be a **dedicated Room table**, for a reason that is
 * enforceable rather than stylistic: the watermark advance must join the same
 * transaction that applies the delta events. `SharedPreferences` cannot join a
 * Room transaction, and `seq_counter` holds the device's *uplink* authorship
 * counter — a different monotonic value about a different thing.
 *
 * The **uplink** watermark needs no storage: `06` §5.4 defines it as the outbox
 * itself, and that is already persisted in `outbox.state`.
 *
 * One row, id [SINGLETON_ID]. A device syncs one incident at a time (`08`
 * §11.1b binds a credential to one incident), so a second row would have no
 * meaning at Level 1.
 */
@Entity(tableName = "sync_state")
data class SyncState(
    @PrimaryKey @ColumnInfo(name = "id") val id: Int = SINGLETON_ID,

    /**
     * The highest `server_seq` whose event has been applied to the local log.
     * `0` means nothing has been applied yet — `server_seq` is a Postgres
     * identity column starting at 1, so 0 is never a real value.
     */
    @ColumnInfo(name = "last_applied_server_seq") val lastAppliedServerSeq: Long = 0L,
) {
    companion object {
        const val SINGLETON_ID: Int = 1
        const val UNSYNCED: Long = 0L
    }
}
