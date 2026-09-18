package ai.rescuenet.field

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEventStore

internal const val DEVICE_ID = 7
internal const val INCIDENT_ID = 9
internal const val TEAM_ID = 3
internal const val DB_NAME = "rescuenet-m6.db"

internal fun context(): Context = ApplicationProvider.getApplicationContext()

internal fun inMemoryDb(): FieldDatabase =
    Room.inMemoryDatabaseBuilder(context(), FieldDatabase::class.java)
        .addCallback(FieldDatabase.SeedSyncState)
        .allowMainThreadQueries()
        .build()

/** File-backed, so it survives process death and reboot. Same path production uses. */
internal fun onDiskDb(): FieldDatabase = FieldDatabase.build(context(), DB_NAME)

internal suspend fun LocalEventStore.appendCellStatus(
    entityId: Long = 214,
    tDev: Long = System.currentTimeMillis(),
): Long = appendAuthored(
    deviceId = DEVICE_ID,
    type = EventType.CELL_STATUS_REPORTED,
    entityType = EntityType.CELL,
    entityId = entityId,
    payload = """{"status":"SEARCHED"}""",
    tDev = tDev,
    schemaVersion = 1,
    responderId = DEVICE_ID,
    teamId = TEAM_ID,
    agencyId = 0,
    incidentId = INCIDENT_ID,
)

internal suspend fun LocalEventStore.appendSurvivor(
    entityId: Long = 1,
    tDev: Long = System.currentTimeMillis(),
): Long = appendAuthored(
    deviceId = DEVICE_ID,
    type = EventType.SURVIVOR_REPORTED,
    entityType = EntityType.SURVIVOR,
    entityId = entityId,
    payload = """{"status":"TRAPPED"}""",
    tDev = tDev,
    schemaVersion = 1,
    responderId = DEVICE_ID,
    teamId = TEAM_ID,
    agencyId = 0,
    incidentId = INCIDENT_ID,
)
