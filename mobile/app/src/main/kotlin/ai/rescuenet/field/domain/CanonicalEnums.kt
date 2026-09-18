package ai.rescuenet.field.domain

/**
 * The 11 Level-1 event types (`08` §2.1–§2.2).
 *
 * There is no duplicate-search type (DM-07), no sync/ack type (DM-08), no audit
 * type (DM-09), and no `REJECTED` — that is an outbox *delivery* state, never an
 * event type (DM-39).
 *
 * Wire codes mirror the backend's `store/codes.py` exactly. They were chosen
 * during M3 from documented orderings and are **awaiting ratification in `08`**;
 * they are not yet settled contract. Codes are permanent once persisted (DM-33).
 */
enum class EventType(val code: Int) {
    // Server-authored control events — 08 §2.1
    INCIDENT_DECLARED(1),
    GRID_GENERATED(2),
    TEAM_REGISTERED(3),
    DEVICE_ENROLLED(4),
    ASSIGNMENT_ISSUED(5),
    ASSIGNMENT_REVOKED(6),

    // Device-authored field events — 08 §2.2
    CELL_STATUS_REPORTED(7),
    SURVIVOR_REPORTED(8),
    RESOURCE_DELTA_REPORTED(9),
    POSITION_REPORTED(10),
    TEAM_STATUS_REPORTED(11);

    companion object {
        private val byCode = entries.associateBy(EventType::code)
        fun fromCode(code: Int): EventType =
            byCode[code] ?: error("Unknown event type code: $code")
    }
}

/** `08` §1.1. `entity_type` is implied by `type` (`09` §10.4). */
enum class EntityType(val code: Int) {
    CELL(1), TEAM(2), SURVIVOR(3), RESOURCE(4),
    INCIDENT(5), GRID(6), DEVICE(7), ASSIGNMENT(8);

    companion object {
        private val byCode = entries.associateBy(EntityType::code)
        fun fromCode(code: Int): EntityType =
            byCode[code] ?: error("Unknown entity type code: $code")
    }
}

/** Server-set provenance (`08` §1.1). Never assigned by the device. */
enum class ReceivedVia(val code: Int) {
    INTERNET(1), SMS(2);

    companion object {
        private val byCode = entries.associateBy(ReceivedVia::code)
        fun fromCode(code: Int): ReceivedVia =
            byCode[code] ?: error("Unknown received_via code: $code")
    }
}

/**
 * Two tiers only (D-04). **Derived from the event type, never stored on the
 * event** (DM-02) — it is an outbox column, computed once at insert.
 *
 * M6 computes and stores this value because the outbox row is written inside
 * M6's atomic transaction. Drain order and scheduling that *consume* it are
 * M7 (`12` §3.4).
 */
enum class Priority {
    CRITICAL, ROUTINE;

    companion object {
        fun of(type: EventType): Priority =
            if (type == EventType.SURVIVOR_REPORTED) CRITICAL else ROUTINE
    }
}
