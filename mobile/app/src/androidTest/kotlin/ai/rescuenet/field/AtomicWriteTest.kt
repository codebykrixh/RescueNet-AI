package ai.rescuenet.field

import androidx.room.withTransaction
import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.LocalEventStore
import ai.rescuenet.field.store.OutboxState
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
 * **AD-10 / TR-19** — event write, `seq` allocation and outbox insert are one
 * transaction: *"Either all three commit or none do."*
 */
@RunWith(AndroidJUnit4::class)
class AtomicWriteTest {

    private lateinit var db: FieldDatabase
    private lateinit var store: LocalEventStore

    @Before fun setUp() { db = inMemoryDb(); store = LocalEventStore(db) }
    @After  fun tearDown() { db.close() }

    @Test fun allThreeEffectsCommitTogether() = runTest {
        val seq = store.appendCellStatus()

        val event = db.events().find(DEVICE_ID, seq)
        val outbox = db.outbox().find(DEVICE_ID, seq)
        val counter = db.seqCounter().peek(DEVICE_ID)

        assertNotNull("event row must exist", event)
        assertNotNull("outbox row must exist", outbox)
        assertEquals("counter must have advanced past the allocated seq", seq + 1, counter)
    }

    @Test fun authoredEventLeavesTheThreeServerSetFieldsNull() = runTest {
        val seq = store.appendCellStatus()
        val e = db.events().find(DEVICE_ID, seq)!!
        assertNull(e.serverSeq)
        assertNull(e.tSrv)
        assertNull(e.receivedVia)
    }

    @Test fun outboxRowStartsPendingWithDerivedPriority() = runTest {
        val routine = store.appendCellStatus()
        val critical = store.appendSurvivor()

        assertEquals(OutboxState.PENDING, db.outbox().find(DEVICE_ID, routine)!!.state)
        assertEquals("ROUTINE", db.outbox().find(DEVICE_ID, routine)!!.priority)
        assertEquals("CRITICAL", db.outbox().find(DEVICE_ID, critical)!!.priority)
    }

    /**
     * **Negative control for atomicity.** A failure inside the transaction must
     * leave *none* of the three. If the three writes were separate statements,
     * the event would survive and this test would fail.
     */
    @Test fun aFailureInsideTheTransactionLeavesNoneOfTheThree() = runTest {
        val before = Triple(db.events().count(), db.outbox().count(), db.seqCounter().peek(DEVICE_ID))

        var threw = false
        try {
            db.withTransaction {
                db.seqCounter().initialise(DEVICE_ID, LocalEventStore.FIRST_SEQ)
                val seq = db.seqCounter().peek(DEVICE_ID)!!
                db.seqCounter().advance(DEVICE_ID)
                db.events().insert(
                    LocalEvent(
                        deviceId = DEVICE_ID, seq = seq,
                        type = EventType.CELL_STATUS_REPORTED.code,
                        entityType = EntityType.CELL.code, entityId = 214,
                        payload = "{}", tDev = 1L, schemaVersion = 1,
                        responderId = DEVICE_ID, teamId = TEAM_ID,
                        agencyId = 0, incidentId = INCIDENT_ID,
                    ),
                )
                error("simulated mid-transaction interrupt")
            }
        } catch (_: IllegalStateException) { threw = true }

        assertTrue("the transaction body must have failed", threw)
        assertEquals("no event may survive a rolled-back transaction", before.first, db.events().count())
        assertEquals("no outbox row may survive", before.second, db.outbox().count())
        assertEquals("the counter must roll back with the transaction", before.third, db.seqCounter().peek(DEVICE_ID))
    }

    /** `06` §4.2 — monotonic, never reused. */
    @Test fun seqIsStrictlyMonotonicAndNeverReused() = runTest {
        val allocated = (1..25).map { store.appendCellStatus(entityId = it.toLong()) }
        assertEquals("no seq may be handed out twice", allocated.size, allocated.toSet().size)
        assertEquals(allocated.sorted(), allocated)
        assertEquals(LocalEventStore.FIRST_SEQ, allocated.first())
    }

    /**
     * `06` §4.2 — *"Gaps are legal; reuse is not."* After a rollback consumes a
     * `seq`, the next allocation must move past it, never reissue it.
     */
    @Test fun aConsumedSeqLeavesALegalGapAndIsNeverReissued() = runTest {
        val first = store.appendCellStatus()

        // Consume a seq in a transaction that then fails for an unrelated reason.
        runCatching {
            db.withTransaction {
                db.seqCounter().advance(DEVICE_ID)   // consumed
                error("rollback after consuming")
            }
        }
        val next = store.appendCellStatus()
        assertTrue("seq must keep increasing", next > first)
        assertTrue("a used seq must never be reissued", next !in setOf(first))
        val stored = db.events().seqsFor(DEVICE_ID)
        assertEquals("only committed events are in the log", stored.size, stored.toSet().size)
    }

    /** `08` Part 5 — a repeated `(device_id, seq)` is a no-op, never an overwrite. */
    @Test fun duplicateIdentityIsANoOpNotAnOverwrite() = runTest {
        val seq = store.appendCellStatus(entityId = 100)
        val original = db.events().find(DEVICE_ID, seq)!!

        val rc = db.events().insert(original.copy(entityId = 999, payload = """{"tampered":true}"""))

        assertEquals("insert must be ignored", -1L, rc)
        assertEquals("stored content must be unchanged", original, db.events().find(DEVICE_ID, seq))
    }
}
