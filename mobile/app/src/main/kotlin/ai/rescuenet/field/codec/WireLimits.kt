package ai.rescuenet.field.codec

/**
 * Every field width and bound of the ratified SMS wire format — **`09` §6.6,
 * DM-57**.
 *
 * These mirror `backend/src/rescuenet/domain/limits.py` exactly, which is the
 * same set derived from the wire schema. `09` §10.5 states the precedent: a
 * limit the wire field cannot represent is a limit of the domain too, "derived
 * from the field width, not chosen independently — the two must never drift
 * apart". Audit finding F-01 is what happens when they drift.
 *
 * **Do not alter a width here without re-ratifying DM-57.**
 */
object WireLimits {

    // ---- framing (09 §6.6.4) — 68 bits, NOT covered by the MAC -------------
    const val BATCH_ID_BITS = 16
    const val PART_INDEX_BITS = 4
    const val PART_TOTAL_BITS = 4
    const val ORIGIN_DEVICE_ID_BITS = 12
    const val MAC_BITS = 32
    const val MAC_BYTES = 4
    const val FRAMING_BITS =
        BATCH_ID_BITS + PART_INDEX_BITS + PART_TOTAL_BITS + ORIGIN_DEVICE_ID_BITS + MAC_BITS

    // ---- header (09 §6.6.1) — nine fields, 89 bits -------------------------
    const val PROTO_VERSION_BITS = 4
    const val DEVICE_ID_BITS = 12
    const val TEAM_ID_BITS = 8
    const val AGENCY_ID_BITS = 4
    const val INCIDENT_ID_BITS = 12
    const val SCHEMA_VERSION_BITS = 4
    const val BASE_SEQ_BITS = 20
    const val BASE_T_BITS = 20
    const val EVENT_COUNT_BITS = 5
    const val HEADER_BITS = PROTO_VERSION_BITS + DEVICE_ID_BITS + TEAM_ID_BITS + AGENCY_ID_BITS +
        INCIDENT_ID_BITS + SCHEMA_VERSION_BITS + BASE_SEQ_BITS + BASE_T_BITS + EVENT_COUNT_BITS

    // ---- event common prefix (09 §6.6.2) -----------------------------------
    const val EVT_TYPE_BITS = 4          // DM-01 Final: widened 3 -> 4
    const val SEQ_DELTA_BITS = 6
    const val T_DELTA_BITS = 12
    const val EVENT_PREFIX_BITS = EVT_TYPE_BITS + SEQ_DELTA_BITS + T_DELTA_BITS

    // ---- payload fields ----------------------------------------------------
    const val CELL_INDEX_BITS = 13
    const val STATUS_BITS = 3
    const val RESPONDER_ID_BITS = 10
    const val PERSON_COUNT_BITS = 6
    const val SURVIVOR_STATUS_BITS = 3
    const val TRIAGE_BITS = 3
    const val TEAM_STATUS_BITS = 3
    const val ITEM_ID_BITS = 8
    const val QTY_DELTA_BITS = 8         // signed
    const val REL_COORD_BITS = 16        // signed
    const val PRESENCE_MASK_BITS = 3

    // ---- ACK (09 §6.6.6) ---------------------------------------------------
    const val ACK_PROTO_BITS = 4
    const val ACK_SEQ_BITS = 20
    const val ACK_BITS = ACK_PROTO_BITS + ACK_SEQ_BITS
    const val ACK_BYTES = 3

    // ---- transport budget (09 §6.6.7, D-02a) -------------------------------
    /** The complete blob: framing ‖ header ‖ events. */
    const val MAX_BATCH_BYTES = 120
    const val FIXED_OVERHEAD_BITS = FRAMING_BITS + HEADER_BITS      // 157
    const val EVENT_CAPACITY_BITS = MAX_BATCH_BYTES * 8 - FIXED_OVERHEAD_BITS  // 803

    // ---- value bounds, mirroring limits.py ---------------------------------
    const val MAX_CELL_INDEX = 8190              // 8191 reserved (09 §10.5)
    const val RESERVED_CELL_INDEX = 8191
    const val MAX_DEVICE_ID = 4095
    const val MAX_TEAM_ID = 255
    const val MAX_AGENCY_ID = 15
    const val MAX_RESPONDER_ID = 1023
    const val MAX_PERSON_COUNT = 63
    const val MAX_ITEM_ID = 255
    const val MIN_QTY_DELTA = -128
    const val MAX_QTY_DELTA = 127
    const val MIN_REL_COORD = -32768
    const val MAX_REL_COORD = 32767
    const val MAX_SEQ = 1_048_575L               // 20-bit
    const val MAX_SEQ_DELTA = 63                 // 6-bit
    const val MAX_T_DELTA = 4095                 // 12-bit seconds
    const val MAX_BASE_T = 1_048_575L            // 20-bit seconds since incident start
    const val MAX_EVENT_COUNT = 31               // 5-bit
    const val MAX_INCIDENT_ID = 4095
    const val MAX_SCHEMA_VERSION = 15
    const val MAX_PROTO_VERSION = 15
    const val MAX_BATCH_ID = 65535
    const val MAX_PART = 15

    /** The wire format this implementation speaks. */
    const val PROTO_VERSION = 1
    const val ACK_PROTO_VERSION = 1
}

/** Raised when a value cannot be represented. **Never** truncate — `08` §10.1 rule 2. */
class WireEncodingException(message: String) : IllegalArgumentException(message)

/** Raised when received bytes are malformed or ambiguous. */
class WireDecodingException(message: String) : IllegalArgumentException(message)
