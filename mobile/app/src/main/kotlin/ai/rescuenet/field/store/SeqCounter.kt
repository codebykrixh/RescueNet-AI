package ai.rescuenet.field.store

import androidx.room.ColumnInfo
import androidx.room.Entity

/**
 * The persisted per-device `seq` counter — **`06` §4.2**.
 *
 * `06` §4.2 requires that `seq` be *"allocated from a persisted counter inside
 * the same local transaction that writes the event"*, and that *"if the
 * transaction rolls back, the seq is consumed and left as a gap. Gaps are
 * legal; reuse is not."*
 *
 * The requirement names a persisted counter but no document specifies its
 * table shape, so this row layout is an M6 implementation detail. What is
 * contract, and what the tests enforce, is the behaviour: monotonic, never
 * reused, allocated inside the write transaction, durable across restart.
 */
@Entity(tableName = "seq_counter")
data class SeqCounter(
    @ColumnInfo(name = "device_id") @androidx.room.PrimaryKey val deviceId: Int,
    /** The next `seq` this device will hand out. Strictly increasing. */
    @ColumnInfo(name = "next_seq") val nextSeq: Long,
)
