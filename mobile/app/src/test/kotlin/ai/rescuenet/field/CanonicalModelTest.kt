package ai.rescuenet.field

import ai.rescuenet.field.domain.EntityType
import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.domain.ReceivedVia
import ai.rescuenet.field.store.LocalEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Pure-JVM parity checks. No Android, no Room — these must run fast and often
 * (`07` row 14).
 */
class CanonicalModelTest {

    /** `08` §2 — exactly 11 Level-1 types. No more, no fewer. */
    @Test fun elevenEventTypes() {
        assertEquals(11, EventType.entries.size)
    }

    /** Codes mirror the backend's `store/codes.py` exactly (M2 model parity). */
    @Test fun eventTypeWireCodesMatchBackend() {
        val expected = mapOf(
            "INCIDENT_DECLARED" to 1, "GRID_GENERATED" to 2, "TEAM_REGISTERED" to 3,
            "DEVICE_ENROLLED" to 4, "ASSIGNMENT_ISSUED" to 5, "ASSIGNMENT_REVOKED" to 6,
            "CELL_STATUS_REPORTED" to 7, "SURVIVOR_REPORTED" to 8,
            "RESOURCE_DELTA_REPORTED" to 9, "POSITION_REPORTED" to 10,
            "TEAM_STATUS_REPORTED" to 11,
        )
        assertEquals(expected, EventType.entries.associate { it.name to it.code })
    }

    @Test fun entityTypeWireCodesMatchBackend() {
        val expected = mapOf(
            "CELL" to 1, "TEAM" to 2, "SURVIVOR" to 3, "RESOURCE" to 4,
            "INCIDENT" to 5, "GRID" to 6, "DEVICE" to 7, "ASSIGNMENT" to 8,
        )
        assertEquals(expected, EntityType.entries.associate { it.name to it.code })
    }

    @Test fun receivedViaWireCodesMatchBackend() {
        assertEquals(mapOf("INTERNET" to 1, "SMS" to 2),
            ReceivedVia.entries.associate { it.name to it.code })
    }

    @Test fun wireCodesRoundTrip() {
        EventType.entries.forEach  { assertEquals(it, EventType.fromCode(it.code)) }
        EntityType.entries.forEach { assertEquals(it, EntityType.fromCode(it.code)) }
        ReceivedVia.entries.forEach { assertEquals(it, ReceivedVia.fromCode(it.code)) }
    }

    /** D-04 / `06` §5.3 — two tiers; only SURVIVOR_REPORTED is CRITICAL at L1. */
    @Test fun priorityIsDerivedFromTypeAlone() {
        assertEquals(Priority.CRITICAL, Priority.of(EventType.SURVIVOR_REPORTED))
        EventType.entries
            .filter { it != EventType.SURVIVOR_REPORTED }
            .forEach { assertEquals("$it should be ROUTINE", Priority.ROUTINE, Priority.of(it)) }
    }

    /**
     * DM-54 — the local row is the 15 canonical fields, and `priority` / `mac`
     * are absent (DM-02, DM-03). Asserted against the declared constructor so a
     * future field addition cannot slip through unnoticed.
     */
    @Test fun localEventHasExactlyTheFifteenCanonicalFields() {
        val params = LocalEvent::class.java.declaredFields
            .map { it.name }
            .filterNot { it.startsWith("$") || it == "Companion" }
            .toSet()
        val canonical = setOf(
            "deviceId", "seq", "type", "entityType", "entityId", "payload", "tDev",
            "schemaVersion", "responderId", "teamId", "agencyId", "incidentId",
            "serverSeq", "tSrv", "receivedVia",
        )
        assertEquals(canonical, params)
        assertEquals(15, params.size)
        assertTrue("priority must not exist on the event (DM-02)", "priority" !in params)
        assertTrue("mac must not exist on the event (DM-03)", "mac" !in params)
    }

    /** DM-54 — the three server-set fields default to null on an authored row. */
    @Test fun serverSetFieldsDefaultToNull() {
        val e = LocalEvent(
            deviceId = 7, seq = 1, type = EventType.CELL_STATUS_REPORTED.code,
            entityType = EntityType.CELL.code, entityId = 214, payload = "{}",
            tDev = 1_700_000_000_000, schemaVersion = 1, responderId = 7,
            teamId = 3, agencyId = 0, incidentId = 9,
        )
        assertNull(e.serverSeq)
        assertNull(e.tSrv)
        assertNull(e.receivedVia)
    }
}
