package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.store.FieldDatabase
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Asserts the *generated SQLite schema*, not the Kotlin source. A field could
 * be renamed, made nullable, or added in Kotlin and still compile; these read
 * `PRAGMA table_info` from the database Room actually created.
 */
@RunWith(AndroidJUnit4::class)
class SchemaShapeTest {

    private lateinit var db: FieldDatabase

    @Before fun setUp() { db = inMemoryDb() }
    @After  fun tearDown() { db.close() }

    private data class Col(val name: String, val notNull: Boolean, val pk: Int)

    private fun columns(table: String): List<Col> {
        val out = mutableListOf<Col>()
        db.openHelper.readableDatabase.query("PRAGMA table_info($table)").use { c ->
            val n = c.getColumnIndexOrThrow("name")
            val nn = c.getColumnIndexOrThrow("notnull")
            val pk = c.getColumnIndexOrThrow("pk")
            while (c.moveToNext()) out += Col(c.getString(n), c.getInt(nn) == 1, c.getInt(pk))
        }
        return out
    }

    /** DM-54 / `08` §1.1 — exactly the 15 canonical fields. */
    @Test fun eventTableHasExactlyFifteenColumns() {
        val cols = columns("event").map { it.name }.toSet()
        assertEquals(
            setOf(
                "device_id", "seq", "type", "entity_type", "entity_id", "payload",
                "t_dev", "schema_version", "responder_id", "team_id", "agency_id",
                "incident_id", "server_seq", "t_srv", "received_via",
            ),
            cols,
        )
        assertEquals(15, cols.size)
    }

    /** DM-02 / DM-03 — neither may appear on the event table. */
    @Test fun eventTableHasNoPriorityAndNoMac() {
        val cols = columns("event").map { it.name }
        assertTrue("priority must not be on the event table (DM-02)", "priority" !in cols)
        assertTrue("mac must not be on the event table (DM-03)", "mac" !in cols)
    }

    /** DM-54 — the three server-set fields are nullable; the other twelve are not. */
    @Test fun onlyTheThreeServerSetFieldsAreNullable() {
        val byName = columns("event").associateBy { it.name }
        val serverSet = setOf("server_seq", "t_srv", "received_via")
        serverSet.forEach {
            assertTrue("$it must be nullable until acknowledged (DM-54)", !byName.getValue(it).notNull)
        }
        byName.keys.filter { it !in serverSet }.forEach {
            assertTrue("$it is device-set and must be NOT NULL (08 §1.3 column A)", byName.getValue(it).notNull)
        }
    }

    /** D-05 / DM-06 — identity is `(device_id, seq)` and nothing else. */
    @Test fun eventPrimaryKeyIsDeviceIdAndSeq() {
        val pk = columns("event").filter { it.pk > 0 }.sortedBy { it.pk }.map { it.name }
        assertEquals(listOf("device_id", "seq"), pk)
    }

    /**
     * `08` §6.1 lists twelve rows; the first names the composite key
     * `device_id, seq`, so the table carries 13 physical columns.
     */
    @Test fun outboxHasAllTwelveDocumentedEntries() {
        val cols = columns("outbox").map { it.name }.toSet()
        assertEquals(
            setOf(
                "device_id", "seq",            // 08 §6.1 row 1 (composite key)
                "state", "priority", "attempt_count", "next_attempt_at",
                "last_error", "batch_ref", "first_queued_at",
                "rejected_code", "rejected_message", "rejected_at", "rejected_batch_ref",
            ),
            cols,
        )
        assertEquals(13, cols.size)
    }

    /** AP-14 / DM-39 — all four rejection columns exist, on the outbox only. */
    @Test fun theFourRejectionColumnsAreOnTheOutboxOnly() {
        val outbox = columns("outbox").map { it.name }
        val event = columns("event").map { it.name }
        listOf("rejected_code", "rejected_message", "rejected_at", "rejected_batch_ref").forEach {
            assertTrue("$it must exist on the outbox (AP-14)", it in outbox)
            assertTrue("$it must NOT exist on the event (DM-39)", it !in event)
        }
    }

    @Test fun seqCounterIsPersistedPerDevice() {
        val cols = columns("seq_counter")
        assertEquals(setOf("device_id", "next_seq"), cols.map { it.name }.toSet())
        assertEquals(listOf("device_id"), cols.filter { it.pk > 0 }.map { it.name })
    }
}
