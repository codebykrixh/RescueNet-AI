package ai.rescuenet.field.transport

import ai.rescuenet.field.domain.Priority

/**
 * What a transport declares about itself — `06` §7.1.
 *
 * The sync layer chooses transports **only by these values, never by name or
 * type** (AD-07/AD-08). That is what lets `PeerTransport` be added at Level 2
 * with no Level-1 change, and it is why nothing in this package exposes a
 * "isSms()" or "isInternet()" predicate for callers to branch on.
 */
data class TransportCapabilities(
    /** Generic size bound, not an SMS concept: Internet declares a large value, SMS a small one. */
    val maxBatchBytes: Int,
    val supportsDownlink: Boolean,
    val latencyClass: LatencyClass,
    val costClass: CostClass,
    val orderingGuaranteed: Boolean,
    val available: Boolean,
)

enum class LatencyClass { FAST, SLOW, VERY_SLOW }
enum class CostClass { FREE, METERED }

/** Handle for one dispatched batch, so the sync layer can correlate the outcome. */
data class SendTicket(val batchRef: Long, val batchId: String)

/** Opaque bytes arriving from a transport. Nothing here parses them. */
data class InboundBatch(val inboundId: String, val bytes: ByteArray) {
    override fun equals(other: Any?) =
        this === other || (other is InboundBatch && inboundId == other.inboundId)
    override fun hashCode() = inboundId.hashCode()
}

/** What happened to a [Transport.send] call, before any per-event verdict is read. */
sealed interface SendOutcome {
    /** The server evaluated the batch. [body] is the opaque `200` payload. */
    data class Evaluated(val body: ByteArray) : SendOutcome
    /**
     * The batch was **not** evaluated per-event. Every event stays `PENDING`
     * — AP-22. [retryableAtRequestLevel] is true only for `500`/`503`.
     */
    data class RequestFailed(
        val httpStatus: Int?,
        val retryableAtRequestLevel: Boolean,
        val detail: String?,
    ) : SendOutcome
}

/**
 * The Level-1 transport interface — **`06` §7.1, verbatim in shape**.
 *
 * Contract obligations, all of them load-bearing:
 *
 *  * `batch` is **opaque bytes**. The transport never inspects, parses or
 *    reorders it (**AD-06**). That is what keeps SMS knowledge out of the sync
 *    layer and codec knowledge out of the transports.
 *  * Transports are selected by [capabilities] alone (**AD-07/AD-08**).
 *  * No transport may block a domain operation; every call is suspending and
 *    off the write path (`06` §5.2 — the local write makes no network call).
 *
 * **M7 implements this interface and [InternetTransport].** `SmsTransport` is
 * **M8** (`12` §3.4), together with the bit-packed codec, `base_seq`/`base_t`
 * framing and the truncated MAC. `PeerTransport` is a Level-2 extension point
 * and is deliberately interface-only — no Level-1 code branches on it, and
 * nothing changes if it never exists (P-8).
 */
interface Transport {

    fun capabilities(): TransportCapabilities

    suspend fun send(batch: ByteArray, priority: Priority): Pair<SendTicket, SendOutcome>

    /** Opaque inbound batches; may be empty. Downlink-capable transports only. */
    suspend fun receive(): List<InboundBatch>

    /** Confirm handled, enabling transport-side cleanup. */
    suspend fun acknowledge(inboundIds: List<String>)
}
