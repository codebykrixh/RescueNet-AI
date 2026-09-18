package ai.rescuenet.field.codec

import ai.rescuenet.field.domain.EventType
import ai.rescuenet.field.store.FieldDatabase
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.time.Instant
import java.time.OffsetDateTime
import java.time.format.DateTimeParseException

/**
 * Resolves the incident epoch that anchors the SMS header's `base_t`
 * (`09` §6.6.1: *"unsigned seconds since incident start"*).
 *
 * **The value is read, never invented.** Its single source is
 * `INCIDENT_DECLARED.started_at` in the device's own event log — the same event,
 * carrying the same ISO-8601 string, that the backend reads when it recomputes
 * the MAC (`services/batch_mac.py`). Both sides therefore derive an identical
 * epoch from an identical string, which is what makes the MAC verifiable at all.
 *
 * `INCIDENT_DECLARED` is server-authored and arrives through the ordinary delta
 * pull (`06` §5.4), so no new table, no new fetch and **no schema change** is
 * needed: M7 already puts it in the log.
 *
 * **Wall-clock time is never substituted.** If the declaring event has not been
 * received the epoch is unknown, [resolve] returns null, and the SMS batch is
 * simply not built — the events stay `PENDING` for a transport that can carry
 * them (`08` §10.1 rule 2). Guessing an epoch would silently corrupt every
 * `base_t` and every MAC derived from it.
 */
class IncidentEpoch(
    private val db: FieldDatabase,
    private val json: Json = Json { ignoreUnknownKeys = true },
) {

    /** @return epoch **seconds** of the incident start, or null if not yet known. */
    suspend fun resolve(incidentId: Int): Long? {
        val declared = db.events()
            .findIncidentDeclared(incidentId, EventType.INCIDENT_DECLARED.code) ?: return null
        val raw = runCatching {
            json.parseToJsonElement(declared.payload).jsonObject["started_at"]?.jsonPrimitive?.content
        }.getOrNull()
        return raw?.let(::parseEpochSeconds)
            // The event exists but carries no usable started_at. Fall back to the
            // event's own t_dev, which the backend also uses in that case.
            ?: (declared.tDev / 1000)
    }

    /**
     * Suspending provider for [SmsBatchEncoder], which needs the epoch as a
     * plain value at pack time.
     */
    suspend fun providerFor(incidentId: Int): () -> Long {
        val epoch = resolve(incidentId)
            ?: throw WireEncodingException(
                "incident $incidentId has no INCIDENT_DECLARED yet, so base_t is unknown; " +
                    "events stay PENDING until the delta pull delivers it"
            )
        return { epoch }
    }

    companion object {
        /**
         * Parses the ISO-8601 `started_at` the backend emits. Accepts an offset
         * (`…+00:00`, `…Z`) and a bare local timestamp, which is read as UTC —
         * matching the backend's own `_to_epoch_seconds`.
         */
        fun parseEpochSeconds(value: String): Long? {
            runCatching { return OffsetDateTime.parse(value).toEpochSecond() }
            runCatching { return Instant.parse(value).epochSecond }
            runCatching {
                return java.time.LocalDateTime.parse(value).toInstant(java.time.ZoneOffset.UTC).epochSecond
            }
            return try {
                value.toLong().let { if (it > 1e12) it / 1000 else it }
            } catch (_: NumberFormatException) {
                null
            } catch (_: DateTimeParseException) {
                null
            }
        }
    }
}
