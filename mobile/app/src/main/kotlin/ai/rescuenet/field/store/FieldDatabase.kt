package ai.rescuenet.field.store

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import android.content.Context
import androidx.room.Room
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * The device's single embedded database — `06` §5.1's "one physical embedded
 * database".
 *
 * Holds the append-only local event log, the outbox, and the persisted `seq`
 * counter. Projections are derived by folding the log (`08` Part 7) and are
 * deliberately not stored here.
 *
 * **No at-rest encryption at Level 1** — `06` §14 records this as an accepted,
 * documented limitation: the database is protected by the OS app sandbox only.
 * Credentials are the exception and live in `EncryptedSharedPreferences`
 * (`07` row 12, `09` §8); see [ai.rescuenet.field.store.DeviceCredentialStore].
 */
@Database(
    entities = [LocalEvent::class, OutboxRow::class, SeqCounter::class, SyncState::class],
    version = 2,
    exportSchema = true,
)
@TypeConverters(OutboxStateConverter::class)
abstract class FieldDatabase : RoomDatabase() {
    abstract fun events(): EventDao
    abstract fun outbox(): OutboxDao
    abstract fun seqCounter(): SeqCounterDao
    abstract fun syncState(): SyncStateDao

    companion object {

        /**
         * The single construction path, so a freshly created database and a
         * migrated one are indistinguishable.
         *
         * Without this, the two diverged: [MIGRATION_1_2] seeds the `sync_state`
         * singleton, but Room's `CREATE TABLE` path does not insert rows, so a
         * new install started with an empty table while an upgraded one did not.
         * Absence is handled safely everywhere (`peek()` maps null to
         * [SyncState.UNSYNCED], and `applyPage` calls `initialise()` inside its
         * own transaction), so this was never a correctness bug — but two
         * start-up states for the same table is a trap, and one of them is not
         * the one the migration test asserts.
         */
        fun build(context: Context, name: String): FieldDatabase =
            Room.databaseBuilder(context.applicationContext, FieldDatabase::class.java, name)
                .addMigrations(MIGRATION_1_2)
                .addCallback(SeedSyncState)
                .build()

        /** Seeds the `sync_state` singleton on first creation. */
        internal val SeedSyncState = object : Callback() {
            override fun onCreate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "INSERT OR IGNORE INTO `sync_state` (`id`, `last_applied_server_seq`) " +
                        "VALUES (${SyncState.SINGLETON_ID}, ${SyncState.UNSYNCED})"
                )
            }
        }

        /**
         * v1 → v2: adds `sync_state` for the downlink watermark (`08` §12.3,
         * DM-55). **Additive only.** No M6 table is touched — the event log,
         * the outbox and the `seq` counter keep the exact shape TR-19 proved
         * durable, so an existing install upgrades without losing a single
         * queued event.
         *
         * The singleton row is seeded here at `0`, so the watermark exists from
         * the moment the migration completes and no code path has to cope with
         * its absence.
         */
        val MIGRATION_1_2: Migration = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `sync_state` (" +
                        "`id` INTEGER NOT NULL, " +
                        "`last_applied_server_seq` INTEGER NOT NULL, " +
                        "PRIMARY KEY(`id`))"
                )
                db.execSQL(
                    "INSERT OR IGNORE INTO `sync_state` (`id`, `last_applied_server_seq`) " +
                        "VALUES (${SyncState.SINGLETON_ID}, ${SyncState.UNSYNCED})"
                )
            }
        }
    }
}

/** Stored as its name so the pruning guard can compare against `'ACKED'` in SQL. */
class OutboxStateConverter {
    @TypeConverter fun toDb(value: OutboxState): String = value.name
    @TypeConverter fun fromDb(value: String): OutboxState = OutboxState.valueOf(value)
}
