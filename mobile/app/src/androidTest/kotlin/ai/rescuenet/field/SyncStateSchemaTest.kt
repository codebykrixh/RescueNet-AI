package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.SyncState
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * `sync_state` shape, and proof that M7 left the M6 tables alone
 * (`12` §3.4 — M6 owns those shapes).
 */
@RunWith(AndroidJUnit4::class)
class SyncStateSchemaTest {

    private lateinit var db: FieldDatabase
    @Before fun setUp() { db = inMemoryDb() }
    @After fun tearDown() = db.close()

    private fun columns(table: String): List<Pair<String, Boolean>> {
        val out = mutableListOf<Pair<String, Boolean>>()
        db.openHelper.readableDatabase.query("PRAGMA table_info($table)").use { c ->
            val n = c.getColumnIndexOrThrow("name"); val nn = c.getColumnIndexOrThrow("notnull")
            while (c.moveToNext()) out += c.getString(n) to (c.getInt(nn) == 1)
        }
        return out
    }

    @Test fun syncStateHasExactlyTheTwoDocumentedColumns() {
        val cols = columns("sync_state")
        assertEquals(setOf("id", "last_applied_server_seq"), cols.map { it.first }.toSet())
        assertTrue("both columns are NOT NULL", cols.all { it.second })
    }

    /** M6 tables must be byte-identical in shape after the M7 upgrade. */
    @Test fun m6TablesAreUnchangedByM7() {
        assertEquals("event must still be the 15 canonical fields", 15, columns("event").size)
        assertEquals("outbox must still be 13 physical columns", 13, columns("outbox").size)
        assertEquals("seq_counter must still be 2 columns", 2, columns("seq_counter").size)
    }

    /** M7 added no outbox column — `12` §3.4 gives it transitions, not schema. */
    @Test fun m7AddedNoOutboxColumn() {
        assertEquals(
            setOf("device_id", "seq", "state", "priority", "attempt_count", "next_attempt_at",
                "last_error", "batch_ref", "first_queued_at",
                "rejected_code", "rejected_message", "rejected_at", "rejected_batch_ref"),
            columns("outbox").map { it.first }.toSet(),
        )
    }

    @Test fun theWatermarkIsASingletonRow() = runTest {
        db.syncState().initialise()
        db.syncState().initialise()
        db.openHelper.readableDatabase.query("SELECT COUNT(*) FROM sync_state").use {
            it.moveToFirst(); assertEquals(1, it.getInt(0))
        }
        assertEquals(SyncState.UNSYNCED, db.syncState().peek())
    }

    /**
     * A freshly created database must start in the *same* state a migrated one
     * does: the singleton row present and at 0. These two paths silently
     * diverged once and must not again.
     */
    @Test fun aFreshlyCreatedDatabaseSeedsTheSingletonRow() = runTest {
        db.openHelper.readableDatabase.query("SELECT id, last_applied_server_seq FROM sync_state").use {
            assertTrue("the singleton row must exist without an explicit initialise()", it.moveToFirst())
            assertEquals(SyncState.SINGLETON_ID, it.getInt(0))
            assertEquals(SyncState.UNSYNCED, it.getLong(1))
            assertEquals(1, it.count)
        }
        assertEquals(SyncState.UNSYNCED, db.syncState().peek())
    }

    @Test fun advanceIsMonotonic() = runTest {
        db.syncState().initialise()
        db.syncState().advanceTo(500)
        assertEquals(500L, db.syncState().peek())
        assertEquals("a lower value must be a no-op", 0, db.syncState().advanceTo(400))
        assertEquals(500L, db.syncState().peek())
        db.syncState().advanceTo(501)
        assertEquals(501L, db.syncState().peek())
    }
}
