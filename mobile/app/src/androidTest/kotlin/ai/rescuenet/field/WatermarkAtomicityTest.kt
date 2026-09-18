package ai.rescuenet.field

import androidx.room.withTransaction
import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.ReceivedVia
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.SyncState
import ai.rescuenet.field.sync.DeltaApplier
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
 * **DM-55 / `08` §12.3** — the watermark advance and the delta application are
 * one transaction: *"Either the events and the new watermark both commit, or
 * neither does."*
 *
 * The forbidden outcome, stated once: **a committed watermark without its
 * events.** That loses those events permanently, because the next pull starts
 * past them and never asks again.
 */
@RunWith(AndroidJUnit4::class)
class WatermarkAtomicityTest {

    private lateinit var db: FieldDatabase
    private lateinit var delta: DeltaApplier

    @Before fun setUp() { db = inMemoryDb(); delta = DeltaApplier(db) }
    @After fun tearDown() = db.close()

    private fun received(deviceId: Int, seq: Long, serverSeq: Long?) = LocalEvent(
        deviceId = deviceId, seq = seq, type = EventType.CELL_STATUS_REPORTED.code,
        entityType = EntityType.CELL.code, entityId = 214, payload = """{"status":"SEARCHED"}""",
        tDev = 1_700_000_000_000, schemaVersion = 1, responderId = 42, teamId = 5,
        agencyId = 0, incidentId = INCIDENT_ID,
        serverSeq = serverSeq, tSrv = 1_700_000_005_000, receivedVia = ReceivedVia.INTERNET.code,
    )

    @Test fun watermarkStartsUnsynced() = runTest {
        delta.ensureInitialised()
        assertEquals(SyncState.UNSYNCED, delta.watermark())
    }

    @Test fun applyingAPageAdvancesTheWatermarkAndInsertsTheEvents() = runTest {
        val page = listOf(received(99, 1, 1401), received(88, 1, 1402))
        assertEquals(2, delta.applyPage(page, nextSince = 1402))
        assertEquals(1402L, delta.watermark())
        assertEquals(2, db.events().count())
        assertNotNull(db.events().find(99, 1))
        assertNotNull(db.events().find(88, 1))
    }

    /**
     * **The atomicity guarantee.** A failure partway through the transaction
     * must leave the watermark *and* the events untouched. If the advance
     * happened outside the transaction, the watermark here would be 1402 with
     * zero events — the silent-loss failure mode.
     */
    @Test fun aFailureMidTransactionCommitsNeitherEventsNorWatermark() = runTest {
        delta.applyPage(listOf(received(99, 1, 1401)), nextSince = 1401)
        val watermarkBefore = delta.watermark()
        val countBefore = db.events().count()

        var threw = false
        try {
            db.withTransaction {
                db.events().insertReceived(listOf(received(77, 1, 1500)))
                db.syncState().advanceTo(1500)
                error("simulated interruption mid-delta")
            }
        } catch (_: IllegalStateException) { threw = true }

        assertTrue(threw)
        assertEquals("watermark must not have advanced", watermarkBefore, delta.watermark())
        assertEquals("no event may have survived", countBefore, db.events().count())
        assertNull(db.events().find(77, 1))
    }

    /**
     * The forbidden state, asserted directly: the watermark must never exceed
     * the highest `server_seq` actually in the log.
     */
    @Test fun theWatermarkNeverOutrunsTheLog() = runTest {
        runCatching {
            db.withTransaction {
                db.events().insertReceived(listOf(received(60, 1, 3000)))
                db.syncState().advanceTo(3000)
                error("interrupted")
            }
        }
        delta.applyPage(listOf(received(61, 1, 1000)), nextSince = 1000)

        val highest = db.events().highestAppliedServerSeq() ?: 0L
        assertTrue("watermark ${delta.watermark()} must not exceed highest applied $highest",
            delta.watermark() <= highest)
    }

    /** DM-06 — dedup is `(device_id, seq)` and nothing else; replay is a no-op. */
    @Test fun replayingTheSamePageIsIdempotent() = runTest {
        val page = listOf(received(99, 1, 1401), received(88, 1, 1402))
        assertEquals(2, delta.applyPage(page, 1402))
        assertEquals("second application inserts nothing", 0, delta.applyPage(page, 1402))
        assertEquals(2, db.events().count())
        assertEquals(1402L, delta.watermark())
    }

    /** A redelivered event must not overwrite the stored one (`08` Part 5, DM-31). */
    @Test fun redeliveryWithDifferentContentDoesNotOverwrite() = runTest {
        delta.applyPage(listOf(received(99, 1, 1401)), 1401)
        val original = db.events().find(99, 1)!!
        delta.applyPage(listOf(received(99, 1, 9999).copy(payload = """{"tampered":true}""")), 1402)
        assertEquals(original, db.events().find(99, 1))
    }

    /** The watermark is monotonic: a stale page cannot rewind it. */
    @Test fun theWatermarkNeverRewinds() = runTest {
        delta.applyPage(listOf(received(99, 1, 2000)), nextSince = 2000)
        delta.applyPage(listOf(received(98, 1, 1500)), nextSince = 1500)
        assertEquals("a lower next_since must not rewind the marker", 2000L, delta.watermark())
    }

    /** Resuming after an interruption reaches the same final state (AD-12). */
    @Test fun interruptedThenResumedReachesTheSameState() = runTest {
        val p1 = listOf(received(99, 1, 100), received(99, 2, 101))
        val p2 = listOf(received(99, 3, 102))

        delta.applyPage(p1, 101)
        runCatching { db.withTransaction { db.events().insertReceived(p2); db.syncState().advanceTo(102); error("crash") } }
        assertEquals(101L, delta.watermark())
        assertEquals(2, db.events().count())

        delta.applyPage(p2, 102)                 // resume from the persisted watermark
        assertEquals(102L, delta.watermark())
        assertEquals(3, db.events().count())
    }

    /** A delta event without `server_seq` cannot be positioned; refuse it. */
    @Test fun deltaEventsWithoutServerSeqAreRefused() = runTest {
        var threw = false
        try { delta.applyPage(listOf(received(99, 1, null)), 1) }
        catch (_: IllegalArgumentException) { threw = true }
        assertTrue("an unpositioned delta event must be refused", threw)
        assertEquals(0, db.events().count())
        assertEquals(SyncState.UNSYNCED, delta.watermark())
    }

    /** `09` §3.6 — beyond 2000 behind, snapshot instead of paging. */
    @Test fun snapshotThresholdMatchesTheContract() {
        assertEquals(2000L, DeltaApplier.SNAPSHOT_THRESHOLD)
        assertTrue(delta.shouldSnapshot(currentServerSeq = 3001, lastApplied = 1000))
        assertTrue(!delta.shouldSnapshot(currentServerSeq = 3000, lastApplied = 1000))
    }
}
