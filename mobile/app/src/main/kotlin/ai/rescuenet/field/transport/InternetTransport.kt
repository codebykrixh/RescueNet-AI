package ai.rescuenet.field.transport

import ai.rescuenet.field.domain.Priority
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * The Level-1 internet transport — `06` §7.2: HTTPS batch POST uplink, HTTPS
 * delta pull downlink.
 *
 * It moves **opaque bytes** and nothing else (**AD-06**). It does not know what
 * an event is, does not parse the batch it sends, and does not interpret the
 * body it receives — the sync layer does that. Keeping the knowledge out of
 * here is what lets `SmsTransport` (M8) slot in behind the same interface.
 *
 * The one thing it *does* interpret is the **HTTP status**, because AP-22 makes
 * request-level outcome a transport-level fact: a `401`/`403`/`413` means the
 * batch was never evaluated per-event, and only `500`/`503` are retryable at
 * the request level. That distinction is returned as [SendOutcome], never
 * guessed at by the caller.
 *
 * **No MAC, no codec, no framing** — all three are M8 (`12` §3.4).
 */
class InternetTransport(
    private val baseUrl: String,
    private val bearerToken: () -> String?,
    private val connectivity: () -> Boolean = { true },
    private val timeoutMs: Int = DEFAULT_TIMEOUT_MS,
) : Transport {

    private val batchRefs = AtomicLong(0)

    override fun capabilities() = TransportCapabilities(
        maxBatchBytes = MAX_BATCH_BYTES,
        supportsDownlink = true,
        latencyClass = LatencyClass.FAST,
        costClass = CostClass.FREE,
        orderingGuaranteed = true,
        available = connectivity(),
    )

    override suspend fun send(
        batch: ByteArray,
        priority: Priority,
    ): Pair<SendTicket, SendOutcome> = withContext(Dispatchers.IO) {
        val ticket = SendTicket(batchRefs.incrementAndGet(), java.util.UUID.randomUUID().toString())
        val outcome = try {
            post("$baseUrl/v1/events", batch)
        } catch (e: IOException) {
            // Transport failure or timeout: the batch was never evaluated, so
            // every event returns to PENDING (08 §6.2, AP-22).
            SendOutcome.RequestFailed(null, retryableAtRequestLevel = true, detail = e.message)
        }
        ticket to outcome
    }

    override suspend fun receive(): List<InboundBatch> = emptyList()

    override suspend fun acknowledge(inboundIds: List<String>) = Unit

    /**
     * Downlink delta pull (`09` §3.1). Returns the opaque response body; the
     * sync layer parses it. Null means the pull failed and the watermark must
     * not move.
     */
    suspend fun fetchDelta(since: Long, limit: Int = DEFAULT_PAGE): ByteArray? =
        withContext(Dispatchers.IO) {
            try {
                get("$baseUrl/v1/events?since=$since&limit=$limit")
            } catch (_: IOException) {
                null
            }
        }

    private fun post(url: String, body: ByteArray): SendOutcome {
        val c = open(url, "POST")
        c.doOutput = true
        c.setRequestProperty("Content-Type", "application/json")
        return try {
            c.outputStream.use { it.write(body) }
            val status = c.responseCode
            if (status == 200) {
                SendOutcome.Evaluated(c.inputStream.use { it.readBytes() })
            } else {
                SendOutcome.RequestFailed(
                    httpStatus = status,
                    // AP-22: only 500 and 503 are retryable at the request level.
                    retryableAtRequestLevel = status == 500 || status == 503,
                    detail = c.errorStream?.use { it.readBytes().decodeToString() },
                )
            }
        } finally {
            c.disconnect()
        }
    }

    private fun get(url: String): ByteArray? {
        val c = open(url, "GET")
        return try {
            if (c.responseCode == 200) c.inputStream.use { it.readBytes() } else null
        } finally {
            c.disconnect()
        }
    }

    private fun open(url: String, method: String): HttpURLConnection =
        (URL(url).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            bearerToken()?.let { setRequestProperty("Authorization", "Bearer $it") }
        }

    companion object {
        /** Generous: `09` §3.5 caps a delta page at 256 KB; uplink batches are far smaller. */
        const val MAX_BATCH_BYTES = 256 * 1024
        const val DEFAULT_TIMEOUT_MS = 15_000
        const val DEFAULT_PAGE = 200
    }
}
