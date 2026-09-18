package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEventStore
import ai.rescuenet.field.store.OutboxRow
import ai.rescuenet.field.store.OutboxState
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * `08` §6.2 state *representation* and `08` §6.3 retention *protection*.
 *
 * The transition engine is M7 (`12` §3.4); these tests write states directly to
 * prove the representation stores all four and that pruning cannot reach the
 * protected ones.
 */
@RunWith(AndroidJUnit4::class)
class RetentionAndStateTest {

    private lateinit var db: FieldDatabase
    private lateinit var store: LocalEventStore

    @Before fun setUp() { db = inMemoryDb(); store = LocalEventStore(db) }
    @After  fun tearDown() { db.close() }

    private suspend fun rowIn(state: OutboxState, entityId: Long): Long {
        val seq = store.appendCellStatus(entityId = entityId)
        val row = db.outbox().find(DEVICE_ID, seq)!!
        db.openHelper.writableDatabase.execSQL(
            "UPDATE outbox SET state = ? WHERE device_id = ? AND seq = ?",
            arrayOf<Any>(state.name, row.deviceId, row.seq),
        )
        return seq
    }

    @Test fun allFourStatesPersistAndReadBack() = runTest {
        OutboxState.entries.forEachIndexed { i, s ->
            val seq = rowIn(s, entityId = 500L + i)
            assertEquals(s, db.outbox().find(DEVICE_ID, seq)!!.state)
        }
    }

    @Test fun theFourRejectionColumnsPersist() = runTest {
        val seq = store.appendCellStatus(entityId = 601)
        val base = db.outbox().find(DEVICE_ID, seq)!!
        db.openHelper.writableDatabase.execSQL(
            "UPDATE outbox SET state='REJECTED', rejected_code=?, rejected_message=?, " +
                "rejected_at=?, rejected_batch_ref=? WHERE device_id=? AND seq=?",
            arrayOf<Any>("UNKNOWN_CELL", "cell 9999 is not in the grid", 1_700_000_000_000L,
                "batch-abc", base.deviceId, base.seq),
        )
        val row: OutboxRow = db.outbox().find(DEVICE_ID, seq)!!
        assertEquals(OutboxState.REJECTED, row.state)
        assertEquals("UNKNOWN_CELL", row.rejectedCode)
        assertEquals("cell 9999 is not in the grid", row.rejectedMessage)
        assertEquals(1_700_000_000_000L, row.rejectedAt)
        assertEquals("batch-abc", row.rejectedBatchRef)
    }

    /**
     * **Negative control for retention.** DM-40: `REJECTED` rows are never
     * pruned. DM-18: `PENDING` rows are never pruned. Only `ACKED` may go.
     */
    @Test fun pruningRemovesAckedRowsOnlyAndNeverTheProtectedOnes() = runTest {
        val pending  = rowIn(OutboxState.PENDING,   701)
        val inFlight = rowIn(OutboxState.IN_FLIGHT, 702)
        val acked    = rowIn(OutboxState.ACKED,     703)
        val rejected = rowIn(OutboxState.REJECTED,  704)

        val removed = db.outbox().pruneAckedRows()

        assertEquals("exactly one ACKED row was prunable", 1, removed)
        assertNotNull("PENDING must survive (DM-18)",  db.outbox().find(DEVICE_ID, pending))
        assertNotNull("IN_FLIGHT must survive",        db.outbox().find(DEVICE_ID, inFlight))
        assertNotNull("REJECTED must survive (DM-40)", db.outbox().find(DEVICE_ID, rejected))
        assertEquals("the ACKED row is gone", null, db.outbox().find(DEVICE_ID, acked))
    }

    /**
     * DM-39 / AP-14 — *"An event is never deleted because it was rejected."*
     * The event survives even when its outbox row is REJECTED, and the FK
     * refuses any attempt to delete the event out from under it.
     */
    @Test fun aRejectedEventRemainsPermanentlyInTheLog() = runTest {
        val seq = rowIn(OutboxState.REJECTED, 801)
        assertNotNull("the domain event must remain auditable", db.events().find(DEVICE_ID, seq))

        val refused = runCatching {
            db.openHelper.writableDatabase.execSQL(
                "DELETE FROM event WHERE device_id = ? AND seq = ?", arrayOf<Any>(DEVICE_ID, seq),
            )
        }.isFailure
        assertEquals("the FK must refuse to orphan an outbox row", true, refused)
        assertNotNull(db.events().find(DEVICE_ID, seq))
    }

    /**
     * Pruning an ACKED outbox row must not touch the event — `08` §6.2:
     * *"outbox row pruned; THE EVENT REMAINS"*.
     */
    @Test fun pruningAnAckedRowLeavesTheEventIntact() = runTest {
        val seq = rowIn(OutboxState.ACKED, 901)
        db.outbox().pruneAckedRows()
        assertNotNull("the event survives outbox pruning", db.events().find(DEVICE_ID, seq))
    }
}
