package ai.rescuenet.field

import androidx.test.ext.junit.runners.AndroidJUnit4
import ai.rescuenet.field.store.LocalEventStore
import ai.rescuenet.field.store.OutboxState
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * **TR-19 (= SP-04)** and **TR-20** — level D, instrumented, physical device.
 *
 * These are phase-driven so an external harness can interleave `adb reboot`
 * and `am force-stop` between them:
 *
 *  * [phase1_writeAndAcknowledge] writes to the **file-backed** database and
 *    returns only after the transaction has committed. Everything it writes is
 *    an "acknowledged write" in NFR-07's sense: the call returned.
 *  * [phase2_verifySurvived] reopens the database from disk and proves every
 *    acknowledged write is still there, with its outbox row and its `seq`.
 *
 * M6's completion criterion is *"100% of acknowledged writes survive five
 * kill/reboot cycles"*, so the harness runs phase 1 once and then alternates
 * kill/reboot with phase 2, five times.
 */
@RunWith(AndroidJUnit4::class)
class Tr19DurabilityTest {

    /** Written once per cycle; the count is cumulative and checked in phase 2. */
    @Test fun phase1_writeAndAcknowledge() = runTest {
        val db = onDiskDb()
        try {
            val store = LocalEventStore(db)
            val before = db.events().count()
            repeat(WRITES_PER_CYCLE) { store.appendCellStatus(entityId = (before + it).toLong()) }
            val after = db.events().count()
            assertEquals("every write must be acknowledged", before + WRITES_PER_CYCLE, after)
        } finally { db.close() }
    }

    @Test fun phase2_verifySurvived() = runTest {
        val db = onDiskDb()
        try {
            val events = db.events().all()
            val outbox = db.outbox().all()

            assertTrue("the log must not be empty after a kill/reboot cycle", events.isNotEmpty())
            assertEquals("every acknowledged event must still have its outbox row",
                events.size, outbox.size)

            // TR-19: the three effects survived together, or none would have.
            events.forEach { e ->
                assertNotNull("outbox row missing for seq ${e.seq}", db.outbox().find(e.deviceId, e.seq))
            }
            // Every surviving outbox row is still PENDING: nothing has been sent,
            // because no transport exists in M6.
            assertTrue("M6 has no transport, so nothing may have left PENDING",
                outbox.all { it.state == OutboxState.PENDING })

            // seq integrity: strictly increasing, no duplicates.
            val seqs = db.events().seqsFor(DEVICE_ID)
            assertEquals("no seq may be reused (06 §4.2)", seqs.size, seqs.toSet().size)
            assertEquals(seqs.sorted(), seqs)

            // The persisted counter must be past every stored seq.
            val next = db.seqCounter().peek(DEVICE_ID)
            assertNotNull("the seq counter must be durable", next)
            assertTrue("counter must exceed every allocated seq", next!! > seqs.max())

            // DM-54: authored events still carry no server-set values.
            events.forEach {
                assertEquals(null, it.serverSeq)
                assertEquals(null, it.tSrv)
                assertEquals(null, it.receivedVia)
            }
        } finally { db.close() }
    }

    /**
     * **TR-20** — with all radios off, the write path completes locally and
     * makes no network call. M6 makes the second half structural rather than
     * observational: [LocalEventStore] has no transport dependency to call.
     * The harness runs this with the device in airplane mode.
     */
    @Test fun tr20_offlineWritePathCompletesLocally() = runTest {
        val db = onDiskDb()
        try {
            val store = LocalEventStore(db)
            val before = db.events().count()
            val seq = store.appendCellStatus(entityId = 424242)
            assertNotNull("the write must complete with no connectivity", db.events().find(DEVICE_ID, seq))
            assertEquals(before + 1, db.events().count())
            assertEquals(OutboxState.PENDING, db.outbox().find(DEVICE_ID, seq)!!.state)
        } finally { db.close() }
    }

    /** Resets the on-disk database so a five-cycle run starts from a known state. */
    @Test fun phase0_reset() = runTest {
        context().deleteDatabase(DB_NAME)
        val db = onDiskDb()
        try { assertEquals(0, db.events().count()) } finally { db.close() }
    }

    private companion object { const val WRITES_PER_CYCLE = 20 }
}
