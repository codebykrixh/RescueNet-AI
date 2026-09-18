package ai.rescuenet.field

import androidx.room.testing.MigrationTestHelper
import androidx.sqlite.db.framework.FrameworkSQLiteOpenHelperFactory
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.SyncState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The v1 → v2 migration that introduces `sync_state` (`08` §12.3, DM-55).
 *
 * The migration is **additive only**: no M6 table is touched, so an existing
 * install upgrades without losing a single queued event. TR-19 proved the M6
 * tables durable; this proves the upgrade does not undo that.
 */
@RunWith(AndroidJUnit4::class)
class MigrationV1ToV2Test {

    @get:Rule
    val helper = MigrationTestHelper(
        InstrumentationRegistry.getInstrumentation(),
        FieldDatabase::class.java,
        emptyList(),
        FrameworkSQLiteOpenHelperFactory(),
    )

    private companion object { const val TEST_DB = "migration-v1-v2.db" }

    /** Room validates the resulting schema against the exported 2.json for us. */
    @Test fun migratesAndValidatesAgainstTheExportedSchema() {
        helper.createDatabase(TEST_DB, 1).close()
        helper.runMigrationsAndValidate(TEST_DB, 2, true, FieldDatabase.MIGRATION_1_2).close()
    }

    /** M6 data written under v1 must survive the upgrade untouched. */
    @Test fun m6DataSurvivesTheUpgrade() {
        helper.createDatabase(TEST_DB, 1).apply {
            execSQL(
                "INSERT INTO event (device_id, seq, type, entity_type, entity_id, payload, t_dev, " +
                    "schema_version, responder_id, team_id, agency_id, incident_id) " +
                    "VALUES (7, 1, 7, 1, 214, '{}', 1700000000000, 1, 7, 3, 0, 9)"
            )
            execSQL(
                "INSERT INTO outbox (device_id, seq, state, priority, attempt_count, first_queued_at) " +
                    "VALUES (7, 1, 'PENDING', 'ROUTINE', 2, 1700000000000)"
            )
            execSQL("INSERT INTO seq_counter (device_id, next_seq) VALUES (7, 2)")
            close()
        }

        val db = helper.runMigrationsAndValidate(TEST_DB, 2, true, FieldDatabase.MIGRATION_1_2)

        db.query("SELECT COUNT(*) FROM event").use { it.moveToFirst(); assertEquals(1, it.getInt(0)) }
        db.query("SELECT state, attempt_count FROM outbox WHERE device_id=7 AND seq=1").use {
            it.moveToFirst()
            assertEquals("PENDING", it.getString(0))
            assertEquals("persisted retry state must survive the migration", 2, it.getInt(1))
        }
        db.query("SELECT next_seq FROM seq_counter WHERE device_id=7").use {
            it.moveToFirst(); assertEquals(2, it.getInt(0))
        }
        db.close()
    }

    /** The migration seeds the singleton watermark row at 0. */
    @Test fun syncStateIsCreatedAndSeeded() {
        helper.createDatabase(TEST_DB, 1).close()
        val db = helper.runMigrationsAndValidate(TEST_DB, 2, true, FieldDatabase.MIGRATION_1_2)
        db.query("SELECT id, last_applied_server_seq FROM sync_state").use {
            assertTrue("the singleton row must exist after migration", it.moveToFirst())
            assertEquals(SyncState.SINGLETON_ID, it.getInt(0))
            assertEquals(SyncState.UNSYNCED, it.getLong(1))
            assertEquals("exactly one row", 1, it.count)
        }
        db.close()
    }

    /** v1 has no sync_state — proving the table is genuinely new, not pre-existing. */
    @Test fun v1HasNoSyncStateTable() {
        val db = helper.createDatabase(TEST_DB, 1)
        db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_state'").use {
            assertEquals("sync_state must not exist at v1", 0, it.count)
        }
        db.close()
    }
}
