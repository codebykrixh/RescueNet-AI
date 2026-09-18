package ai.rescuenet.field.store

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

/**
 * Reads and writes the downlink watermark (`08` §12.3, DM-55).
 *
 * Nothing here opens a transaction. That is deliberate: the watermark advance
 * is only ever legal *inside* the caller's delta transaction, and a DAO that
 * could commit on its own would make the illegal call easy to write. See
 * [ai.rescuenet.field.sync.DeltaApplier].
 */
@Dao
interface SyncStateDao {

    @Query("SELECT last_applied_server_seq FROM sync_state WHERE id = :id")
    suspend fun peek(id: Int = SyncState.SINGLETON_ID): Long?

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun initialise(row: SyncState = SyncState())

    /**
     * Monotonic by construction: the guard makes a lower value a no-op rather
     * than a silent rewind. A rewind would re-request events the device already
     * has — harmless to correctness thanks to `(device_id, seq)` dedup, but it
     * would mean the marker no longer describes the log.
     */
    @Query(
        "UPDATE sync_state SET last_applied_server_seq = :serverSeq " +
            "WHERE id = :id AND :serverSeq > last_applied_server_seq"
    )
    suspend fun advanceTo(serverSeq: Long, id: Int = SyncState.SINGLETON_ID): Int
}
