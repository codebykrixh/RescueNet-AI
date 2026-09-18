package ai.rescuenet.field.transport

import ai.rescuenet.field.codec.AckCodec
import ai.rescuenet.field.codec.SmsAck
import ai.rescuenet.field.codec.WireDecodingException
import ai.rescuenet.field.codec.WireLimits
import ai.rescuenet.field.domain.Priority
import java.util.Base64
import java.util.concurrent.atomic.AtomicLong

/**
 * The Level-1 SMS transport — `06` §7.2, `09` §6, **D-02a Final**.
 *
 * Carries **opaque bytes** and nothing else (AD-06): it does not know what an
 * event is, does not parse the blob it sends, and does not interpret the ACK it
 * receives. Encoding is the codec's job; eligibility and batching belong to
 * [ai.rescuenet.field.sync.SmsBatchEncoder].
 *
 * **Capabilities** are what the sync layer selects on, never the class name
 * (AD-07/AD-08): `VERY_SLOW`, `METERED`, `maxBatchBytes` **120 B**. AD-09 then
 * keeps `ROUTINE` traffic off this link while internet is absent, and DM-56
 * gives it the slow SMS backoff — **this class implements no retry of its own**.
 *
 * **Uplink only, ACK downlink** (D-06). **GSM-7 text only** — no binary path
 * exists here to call.
 */
class SmsTransport(
    private val gatewayNumber: String,
    private val sender: SmsSender,
    private val available: () -> Boolean = { true },
) : Transport {

    private val batchRefs = AtomicLong(0)
    private val inbox = ArrayDeque<InboundBatch>()

    override fun capabilities() = TransportCapabilities(
        maxBatchBytes = WireLimits.MAX_BATCH_BYTES,   // 120 B, D-02a
        supportsDownlink = true,                      // ACK only (D-06)
        latencyClass = LatencyClass.VERY_SLOW,
        costClass = CostClass.METERED,
        orderingGuaranteed = false,                   // SMS may reorder; observed in SP-01b-A Q3
        available = available(),
    )

    /**
     * Sends one packed batch as a single GSM-7 text message.
     *
     * The blob is base64url-encoded without padding: 120 B → exactly 160
     * characters, and every base64url character is in the GSM 03.38 default
     * alphabet, so it costs one septet and the message stays **single-segment**
     * (`09` §6.6.7, M8-12).
     *
     * A blob over budget is **refused, never truncated** (`08` §10.1 rule 2) —
     * the caller leaves those events `PENDING`.
     */
    override suspend fun send(batch: ByteArray, priority: Priority): Pair<SendTicket, SendOutcome> {
        val ticket = SendTicket(batchRefs.incrementAndGet(), java.util.UUID.randomUUID().toString())
        if (batch.size > WireLimits.MAX_BATCH_BYTES) {
            return ticket to SendOutcome.RequestFailed(
                httpStatus = null, retryableAtRequestLevel = false,
                detail = "blob ${batch.size} B exceeds the ${WireLimits.MAX_BATCH_BYTES} B SMS budget",
            )
        }
        val text = encodeToText(batch)
        if (text.length > SINGLE_SEGMENT_CHARS) {
            return ticket to SendOutcome.RequestFailed(
                null, false, "encoded ${text.length} chars exceeds the $SINGLE_SEGMENT_CHARS-septet single segment",
            )
        }
        val accepted = sender.sendText(gatewayNumber, text)
        // The gateway acknowledges out of band, so a successful hand-off is not an
        // acceptance verdict. Events stay IN_FLIGHT until an ACK arrives; a refused
        // hand-off is a retryable transport failure under DM-56's SMS backoff.
        return ticket to SendOutcome.RequestFailed(
            httpStatus = null,
            retryableAtRequestLevel = true,
            detail = if (accepted) "handed to the SMS sender; awaiting gateway ACK" else "the SMS sender refused the send",
        )
    }

    /** Inbound ACK batches, delivered by the platform receiver. Opaque to this class. */
    override suspend fun receive(): List<InboundBatch> {
        val out = inbox.toList(); inbox.clear(); return out
    }

    override suspend fun acknowledge(inboundIds: List<String>) {
        inbox.removeAll { it.inboundId in inboundIds }
    }

    /** Called by the platform SMS receiver with a raw inbound body. */
    fun onInboundText(body: String) {
        runCatching { decodeFromText(body) }.onSuccess {
            inbox.addLast(InboundBatch(java.util.UUID.randomUUID().toString(), it))
        }
    }

    /** Parses a 3-byte ACK from an inbound blob (`09` §6.6.6). */
    fun parseAck(bytes: ByteArray): SmsAck? =
        runCatching { AckCodec.decode(bytes) }.getOrElse { if (it is WireDecodingException) null else throw it }

    companion object {
        /** GSM-7 single-segment capacity in septets. */
        const val SINGLE_SEGMENT_CHARS = 160

        private val ENC: Base64.Encoder = Base64.getUrlEncoder().withoutPadding()
        private val DEC: Base64.Decoder = Base64.getUrlDecoder()

        /** base64url, RFC 4648 §5, **no padding** (`09` §6.6.7). */
        fun encodeToText(blob: ByteArray): String = ENC.encodeToString(blob)

        fun decodeFromText(text: String): ByteArray = DEC.decode(text)
    }
}
