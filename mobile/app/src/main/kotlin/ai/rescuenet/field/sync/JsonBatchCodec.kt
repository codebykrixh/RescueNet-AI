package ai.rescuenet.field.sync

import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.LocalEvent
import ai.rescuenet.field.store.OutboxRow
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.encodeToJsonElement

/**
 * The JSON batch format of `09` §2.2 — the only encoding M7 owns.
 *
 * Built on **`kotlinx.serialization`**, which is the ratified mobile choice
 * (`07` row 13, **T-16 FINAL**, and the approved Mobile row of `12` §4).
 * Android's framework `org.json` is deliberately *not* used: it is absent from
 * the `12` §4 approved table, and on the JVM unit-test classpath it is a stub
 * that returns defaults, so parsing tests written against it pass without
 * parsing anything.
 *
 * **This is not the wire codec.** The bit-packed encoding, `base_seq`/`base_t`
 * batch header, SMS framing and truncated MAC are all **M8** (`08` Parts 9–10,
 * AD-07, DM-49). Nothing here packs bits or computes a MAC — `09` §2.2 makes
 * `mac` *"Required only when forwarded by a gateway… Absent on direct TLS
 * uploads"*, which is the path this encoder serves.
 *
 * Server-assigned fields are omitted from the request: `09` §2.2 sends events
 * *"without server-assigned fields"*, and under DM-54 the device does not have
 * them yet anyway.
 */
class JsonBatchCodec(
    private val json: Json = Json {
        ignoreUnknownKeys = true      // 09 §2.6.1 — a new server field must not break an old client
        encodeDefaults = true
        explicitNulls = false
    },
) : BatchEncoder, VerdictParser {

    override fun fit(rows: List<OutboxRow>, maxBatchBytes: Int): List<OutboxRow> {
        if (rows.isEmpty()) return rows
        val budget = maxBatchBytes - ENVELOPE_OVERHEAD_BYTES
        if (budget <= 0) return emptyList()
        val fits = budget / ESTIMATED_EVENT_BYTES
        return if (fits <= 0) rows.take(1) else rows.take(fits)
    }

    override suspend fun encode(rows: List<OutboxRow>, db: FieldDatabase): ByteArray {
        val events = rows.mapNotNull { db.events().find(it.deviceId, it.seq)?.toRequest() }
        val batch = BatchRequest(
            batchId = java.util.UUID.randomUUID().toString(),
            originDeviceId = events.firstOrNull()?.deviceId ?: 0,
            events = events,
        )
        return json.encodeToString(BatchRequest.serializer(), batch).toByteArray()
    }

    /**
     * `09` §2.3. Duplicates arrive in `accepted` with `was_duplicate: true`,
     * never in `rejected` (AP-05, AD-28) — preserved rather than normalised.
     *
     * `retryable` is read as a boolean and **`code` is never inspected**
     * (AP-21); it is carried through verbatim for diagnostics only.
     */
    override fun parse(body: ByteArray): BatchVerdict {
        val dto = json.decodeFromString(BatchResponse.serializer(), body.decodeToString())
        return BatchVerdict(
            accepted = dto.accepted.map {
                AcceptedEvent(it.deviceId, it.seq, it.serverSeq, it.wasDuplicate)
            },
            rejected = dto.rejected.map {
                RejectedEvent(it.deviceId, it.seq, it.code, it.retryable, it.message)
            },
            serverSeqHigh = dto.serverSeqHigh,
        )
    }

    /** Parses a delta page (`09` §3.4) into canonical rows with their server-set fields. */
    fun parseDelta(body: ByteArray): DeltaPage {
        val dto = json.decodeFromString(DeltaResponse.serializer(), body.decodeToString())
        return DeltaPage(
            events = dto.events.map { it.toLocalEvent() },
            nextSince = dto.nextSince,
            hasMore = dto.hasMore,
            currentServerSeq = dto.currentServerSeq,
        )
    }

    private fun LocalEvent.toRequest() = EventDto(
        deviceId = deviceId, seq = seq, type = type, entityType = entityType,
        entityId = entityId, payload = json.parseToJsonElement(payload),
        tDev = tDev, schemaVersion = schemaVersion, responderId = responderId,
        teamId = teamId, agencyId = agencyId, incidentId = incidentId,
        // server_seq, t_srv, received_via deliberately absent — 09 §2.2, DM-54.
    )

    private fun EventDto.toLocalEvent() = LocalEvent(
        deviceId = deviceId, seq = seq, type = type, entityType = entityType,
        entityId = entityId,
        payload = (payload as? JsonObject)?.toString() ?: payload?.toString() ?: "{}",
        tDev = tDev, schemaVersion = schemaVersion, responderId = responderId,
        teamId = teamId, agencyId = agencyId, incidentId = incidentId,
        serverSeq = serverSeq, tSrv = tSrv, receivedVia = receivedVia,
    )

    companion object {
        const val ENVELOPE_OVERHEAD_BYTES = 128
        /** Conservative per-event JSON estimate; the transport's budget is the real bound. */
        const val ESTIMATED_EVENT_BYTES = 320
    }
}

// ─────────────────────────── wire DTOs — 09 §2.2, §2.3, §3.4 ───────────────

@Serializable
internal data class BatchRequest(
    @SerialName("batch_id") val batchId: String,
    @SerialName("origin_device_id") val originDeviceId: Int,
    val events: List<EventDto>,
)

@Serializable
internal data class EventDto(
    @SerialName("device_id") val deviceId: Int,
    val seq: Long,
    val type: Int,
    @SerialName("entity_type") val entityType: Int,
    @SerialName("entity_id") val entityId: Long,
    val payload: JsonElement? = null,
    @SerialName("t_dev") val tDev: Long,
    @SerialName("schema_version") val schemaVersion: Int,
    @SerialName("responder_id") val responderId: Int,
    @SerialName("team_id") val teamId: Int,
    @SerialName("agency_id") val agencyId: Int,
    @SerialName("incident_id") val incidentId: Int,
    @SerialName("server_seq") val serverSeq: Long? = null,
    @SerialName("t_srv") val tSrv: Long? = null,
    @SerialName("received_via") val receivedVia: Int? = null,
)

@Serializable
internal data class BatchResponse(
    val accepted: List<AcceptedDto> = emptyList(),
    val rejected: List<RejectedDto> = emptyList(),
    @SerialName("server_seq_high") val serverSeqHigh: Long? = null,
)

@Serializable
internal data class AcceptedDto(
    @SerialName("device_id") val deviceId: Int,
    val seq: Long,
    @SerialName("server_seq") val serverSeq: Long? = null,
    @SerialName("was_duplicate") val wasDuplicate: Boolean = false,
)

@Serializable
internal data class RejectedDto(
    @SerialName("device_id") val deviceId: Int,
    val seq: Long,
    val code: String = "UNSPECIFIED",
    /**
     * AP-21: the boolean is authoritative. A response omitting it is treated as
     * permanent, matching `09` §2.6 — `UNAVAILABLE` is the only retryable
     * verdict and it always sets the flag.
     */
    val retryable: Boolean = false,
    val message: String? = null,
)

@Serializable
internal data class DeltaResponse(
    val events: List<EventDto> = emptyList(),
    @SerialName("next_since") val nextSince: Long = 0L,
    @SerialName("has_more") val hasMore: Boolean = false,
    @SerialName("current_server_seq") val currentServerSeq: Long = 0L,
)

/** One page of `GET /v1/events?since=…` — `09` §3.4. */
data class DeltaPage(
    val events: List<LocalEvent>,
    val nextSince: Long,
    val hasMore: Boolean,
    val currentServerSeq: Long,
)
