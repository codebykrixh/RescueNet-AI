package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.ReceivedVia
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.LocalEventStore
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * `08` Part 12 and **DM-54** — one append-only log holds **both** events the
 * device authored and events it received. A received row differs from an
 * authored one in exactly one way: it already carries the three server-set
 * fields, because the server assigned them at acceptance.
 *
 * This exercises the *representation* only. **Delta application** — deciding
 * what to fetch, applying it, and advancing `last_applied_server_seq` — is
 * **M7** (`12` §3.4) and is deliberately absent.
 */
@RunWith(AndroidJUnit4::class)
class ReceivedEventTest {

    private lateinit var db: FieldDatabase
    private lateinit var store: LocalEventStore

    @Before fun setUp() { db = inMemoryDb(); store = LocalEventStore(db) }
    @After  fun tearDown() { db.close() }

    private fun received(deviceId: Int, seq: Long, serverSeq: Long) = LocalEvent(
        deviceId = deviceId, seq = seq,
        type = EventType.CELL_STATUS_REPORTED.code,
        entityType = EntityType.CELL.code, entityId = 214,
        payload = """{"status":"SEARCHED"}""",
        tDev = 1_700_000_000_000, schemaVersion = 1,
        responderId = 42, teamId = 5, agencyId = 0, incidentId = INCIDENT_ID,
        serverSeq = serverSeq,
        tSrv = 1_700_000_005_000,
        receivedVia = ReceivedVia.INTERNET.code,
    )

    @Test fun aReceivedEventRoundTripsWithAllThreeServerSetFields() = runTest {
        db.events().insert(received(deviceId = 99, seq = 4, serverSeq = 1234))

        val e = db.events().find(99, 4)!!
        assertEquals(1234L, e.serverSeq)
        assertEquals(1_700_000_005_000L, e.tSrv)
        assertEquals(ReceivedVia.INTERNET.code, e.receivedVia)
        assertEquals(ReceivedVia.INTERNET, ReceivedVia.fromCode(e.receivedVia!!))
    }

    /** SMS provenance must persist as distinctly as INTERNET (`08` §1.1). */
    @Test fun smsProvenanceIsStoredDistinctly() = runTest {
        db.events().insert(received(98, 1, 10).copy(receivedVia = ReceivedVia.SMS.code))
        assertEquals(ReceivedVia.SMS, ReceivedVia.fromCode(db.events().find(98, 1)!!.receivedVia!!))
    }

    /**
     * Part 12: one store, both kinds. Authored rows carry null server-set
     * fields; received rows carry values. Both live in the same table.
     */
    @Test fun authoredAndReceivedCoexistInOneLog() = runTest {
        val mine = store.appendCellStatus(entityId = 7)
        db.events().insert(received(deviceId = 99, seq = 1, serverSeq = 500))
        db.events().insert(received(deviceId = 88, seq = 2, serverSeq = 501))

        assertEquals(3, db.events().count())
        assertNull("my authored row has no server_seq yet", db.events().find(DEVICE_ID, mine)!!.serverSeq)
        assertNotNull(db.events().find(99, 1)!!.serverSeq)
        assertNotNull(db.events().find(88, 2)!!.serverSeq)
    }

    /**
     * A received event has **no outbox row** — the outbox holds *authored,
     * not-yet-acknowledged* events only (`06` §5.1).
     */
    @Test fun receivedEventsGetNoOutboxRow() = runTest {
        db.events().insert(received(99, 1, 500))
        assertEquals(0, db.outbox().count())
        assertNull(db.outbox().find(99, 1))
    }

    /**
     * DM-31 — the same identity cannot carry different content, and a second
     * arrival never overwrites. Set union, never replacement (`08` Part 5).
     */
    @Test fun redeliveryOfAReceivedEventIsANoOp() = runTest {
        db.events().insert(received(99, 1, 500))
        val original = db.events().find(99, 1)!!

        val rc = db.events().insert(received(99, 1, 999).copy(payload = """{"tampered":true}"""))

        assertEquals("redelivery must be ignored", -1L, rc)
        assertEquals("content must be unchanged", original, db.events().find(99, 1))
    }

    /**
     * Two devices reporting the same cell are two facts, both kept — the D-01b
     * duplicate-search scenario (`08` Part 5, DM-15).
     */
    @Test fun twoDevicesReportingTheSameCellBothSurvive() = runTest {
        db.events().insert(received(deviceId = 99, seq = 1, serverSeq = 600))
        db.events().insert(received(deviceId = 88, seq = 1, serverSeq = 601))

        assertEquals("both observations are true and both must survive", 2, db.events().count())
        assertNotNull(db.events().find(99, 1))
        assertNotNull(db.events().find(88, 1))
    }
}
