package ai.rescuenet.field.codec

import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.store.LocalEvent
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * Maps canonical [LocalEvent] rows to [WireEvent] — and refuses everything the
 * SMS path does not carry.
 *
 * This is a **representation** change only (`08` §10.1 rule 3): no reordering,
 * merging, dropping or synthesis, and no semantic decision. Priority and
 * batching live above it; bit layout lives below it.
 *
 * **SCOPE A** (M8-6). `POSITION_REPORTED` is refused outright — `09` §6.3 makes
 * that absolute (M8-7) — as are the six server-authored types, which have no
 * SMS layout and must not be given one.
 *
 * `TEAM_STATUS_REPORTED.note` is silently *not carried* because `08` Part 9
 * states it is never sent over SMS. That is not truncation of a transmitted
 * value: the field is outside the SMS representation by contract, and the
 * event's canonical record in the local log keeps it intact.
 */
class WireEventMapper(private val json: Json = Json { ignoreUnknownKeys = true }) {

    /** Types the SMS uplink carries. Everything else is refused. */
    val smsEligible: Set<EventType> = setOf(
        EventType.CELL_STATUS_REPORTED,
        EventType.SURVIVOR_REPORTED,
        EventType.RESOURCE_DELTA_REPORTED,
        EventType.TEAM_STATUS_REPORTED,
    )

    fun isSmsEligible(e: LocalEvent): Boolean =
        runCatching { EventType.fromCode(e.type) }.getOrNull() in smsEligible

    /**
     * @param seqDelta `event.seq - base_seq`
     * @param tDelta   whole seconds from `base_t` to the event's `t_dev`
     * @throws WireEncodingException if the type has no SMS layout or a value does not fit
     */
    fun toWire(e: LocalEvent, seqDelta: Int, tDelta: Int): WireEvent {
        val type = runCatching { EventType.fromCode(e.type) }.getOrNull()
            ?: throw WireEncodingException("unknown event type code ${e.type}")
        if (type !in smsEligible) {
            throw WireEncodingException(
                if (type == EventType.POSITION_REPORTED)
                    "POSITION_REPORTED is never sent over SMS (09 §6.3, M8-7)"
                else
                    "$type has no SMS layout — SCOPE A carries only $smsEligible (M8-6)"
            )
        }
        val p = json.parseToJsonElement(e.payload).jsonObject
        fun int(k: String): Int = p[k]?.jsonPrimitive?.content?.toIntOrNull()
            ?: throw WireEncodingException("payload field '$k' missing or not an integer for $type")
        fun str(k: String): String = p[k]?.jsonPrimitive?.content
            ?: throw WireEncodingException("payload field '$k' missing for $type")
        fun intOrNull(k: String): Int? = p[k]?.jsonPrimitive?.content?.toIntOrNull()
        fun strOrNull(k: String): String? = p[k]?.jsonPrimitive?.contentOrNullSafe()

        return when (type) {
            EventType.CELL_STATUS_REPORTED -> WireEvent.CellStatusReported(
                seqDelta, tDelta,
                cellIndex = int("cell_index"),
                status = enumOrThrow(str("status")) { CellStatus.valueOf(it) },
                responderId = e.responderId,
            )
            EventType.RESOURCE_DELTA_REPORTED -> WireEvent.ResourceDeltaReported(
                seqDelta, tDelta,
                itemId = int("item_id"),
                qtyDelta = int("qty_delta"),
                responderId = e.responderId,
            )
            EventType.TEAM_STATUS_REPORTED -> WireEvent.TeamStatusReported(
                seqDelta, tDelta,
                teamStatus = enumOrThrow(str("team_status")) { TeamStatus.valueOf(it) },
                responderId = e.responderId,
            )
            EventType.SURVIVOR_REPORTED -> WireEvent.SurvivorReported(
                seqDelta, tDelta,
                cellIndex = int("cell_index"),
                personCount = int("person_count"),
                survivorStatus = enumOrThrow(str("survivor_status")) { SurvivorStatus.valueOf(it) },
                triage = strOrNull("triage")?.let { t -> enumOrThrow(t) { Triage.valueOf(it) } },
                relLat = intOrNull("rel_lat"),
                relLon = intOrNull("rel_lon"),
                responderId = e.responderId,
            )
            else -> throw WireEncodingException("unreachable: $type")
        }
    }

    private fun <T> enumOrThrow(raw: String, f: (String) -> T): T =
        runCatching { f(raw) }.getOrElse { throw WireEncodingException("unknown enum value '$raw'") }

    private fun kotlinx.serialization.json.JsonPrimitive.contentOrNullSafe(): String? =
        if (this is kotlinx.serialization.json.JsonNull) null else content
}
