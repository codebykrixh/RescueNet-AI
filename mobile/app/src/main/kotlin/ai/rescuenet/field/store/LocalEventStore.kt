package ai.rescuenet.field.store

import androidx.room.withTransaction
import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.Priority

/**
 * M6's single responsibility: **append an authored event, allocate its `seq`,
 * and queue it — atomically**.
 *
 * `06` §5.1 / **AD-10**: *"the event write, the seq allocation and the outbox
 * insert occur in one transaction. Either all three commit or none do."*
 * That is what [appendAuthored] guarantees, and it is what TR-19 / SP-04
 * measures.
 *
 * `06` §5.2: **no network call exists on this path.** This class has no
 * transport dependency and cannot acquire one — transports are M7.
 *
 * Deliberately absent, because they are **M7** (`12` §3.4): outbox state
 * transitions, retry and backoff, priority drain order, transport selection,
 * ACK/REJECT processing, `IN_FLIGHT` → `PENDING` restart recovery, delta
 * application, and the `last_applied_server_seq` watermark. Also absent because
 * they are **M8**: the bit-packed codec, SMS framing and batch MAC.
 */
class LocalEventStore(private val db: FieldDatabase) {

    /**
     * Writes one device-authored event.
     *
     * All three effects — `seq` allocation from the persisted counter, the
     * event row, and the `PENDING` outbox row — commit together or not at all.
     * If the body throws, Room rolls the whole transaction back; the counter
     * reverts with it, so no `seq` is stranded by an *internal* failure. A
     * crash between commit boundaries can still consume a `seq` and leave a
     * gap, which `06` §4.2 declares legal. **Reuse is not.**
     *
     * The three server-set fields (`server_seq`, `t_srv`, `received_via`) are
     * left null: the device cannot know them at write time (DM-54).
     *
     * @return the allocated `seq`.
     */
    suspend fun appendAuthored(
        deviceId: Int,
        type: EventType,
        entityType: EntityType,
        entityId: Long,
        payload: String,
        tDev: Long,
        schemaVersion: Int,
        responderId: Int,
        teamId: Int,
        agencyId: Int,
        incidentId: Int,
        now: Long = tDev,
    ): Long = db.withTransaction {
        val counters = db.seqCounter()
        counters.initialise(deviceId, FIRST_SEQ)
        val seq = counters.peek(deviceId)
            ?: error("seq counter missing for device $deviceId after initialise")
        counters.advance(deviceId)

        val inserted = db.events().insert(
            LocalEvent(
                deviceId = deviceId,
                seq = seq,
                type = type.code,
                entityType = entityType.code,
                entityId = entityId,
                payload = payload,
                tDev = tDev,
                schemaVersion = schemaVersion,
                responderId = responderId,
                teamId = teamId,
                agencyId = agencyId,
                incidentId = incidentId,
                // server-set — unknown at authorship (08 §1.3 column B, DM-54)
                serverSeq = null,
                tSrv = null,
                receivedVia = null,
            ),
        )
        check(inserted != -1L) { "seq $seq already used by device $deviceId — reuse is not legal (06 §4.2)" }

        db.outbox().insert(
            OutboxRow(
                deviceId = deviceId,
                seq = seq,
                state = OutboxState.PENDING,
                priority = Priority.of(type).name,
                attemptCount = 0,
                nextAttemptAt = null,
                lastError = null,
                batchRef = null,
                firstQueuedAt = now,
            ),
        )
        seq
    }

    companion object {
        /** `seq` is 20-bit on the wire (`08` §1.1); allocation starts at 1. */
        const val FIRST_SEQ: Long = 1L
    }
}
