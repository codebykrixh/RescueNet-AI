package ai.rescuenet.field.sync

import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.store.FieldDatabase
import ai.rescuenet.field.store.OutboxRow
import ai.rescuenet.field.transport.SendOutcome
import ai.rescuenet.field.transport.Transport
import ai.rescuenet.field.transport.TransportSelector

/**
 * Orchestrates one reconnection cycle — `06` §5.4:
 *
 *  1. **Uplink** — drain the outbox by priority, CRITICAL first.
 *  2. **Downlink** — delta-pull from `last_applied_server_seq`.
 *
 * Both directions are driven by persisted monotonic markers and both are
 * idempotent, so interrupting and repeating any step produces the same final
 * state (**AD-12**).
 *
 * This class contains **no encoding**. It hands the codec's output to a
 * transport as opaque bytes (AD-06); the codec itself, SMS framing and the
 * batch MAC are **M8** (`12` §3.4). [BatchEncoder] is the seam — M7 ships the
 * JSON encoder the `InternetTransport` needs and nothing more.
 */
class SyncEngine(
    private val db: FieldDatabase,
    private val outbox: OutboxEngine,
    private val delta: DeltaApplier,
    private val selector: TransportSelector,
    private val encoder: BatchEncoder,
    private val verdictParser: VerdictParser,
    private val clock: () -> Long = System::currentTimeMillis,
) {

    /**
     * Call once at process start, **before** any drain — `08` §6.3 "After
     * restart". Reclaims `IN_FLIGHT` rows left behind by a kill or crash and
     * seeds the watermark row.
     */
    suspend fun onStart(): Int {
        delta.ensureInitialised()
        return outbox.recoverAfterRestart()
    }

    /**
     * One uplink pass. Drains CRITICAL before ROUTINE because the DAO orders by
     * priority (`06` §5.3) — the tier is read from the outbox row, which M6
     * derived from the event type at insert (DM-02). **Nothing here reads the
     * event type**, and nothing selects a transport by name (AD-08).
     */
    suspend fun drainOnce(limit: Int = DEFAULT_BATCH): DrainResult {
        val now = clock()
        val rows = outbox.nextBatch(now, limit)
        if (rows.isEmpty()) return DrainResult.NothingToSend

        val priority = if (rows.any { it.priority == Priority.CRITICAL.name })
            Priority.CRITICAL else Priority.ROUTINE

        val transport: Transport = selector.select(priority)
            ?: return DrainResult.NoTransport   // 06 §7.3 rule 3: remain PENDING

        val capabilities = transport.capabilities()
        val sendable = encoder.fit(rows, capabilities.maxBatchBytes)
        if (sendable.isEmpty()) return DrainResult.NothingToSend

        val payload = encoder.encode(sendable, db)
        val (ticket, outcome) = transport.send(payload, priority)
        outbox.markBatchInFlight(sendable, ticket.batchRef)

        return when (outcome) {
            is SendOutcome.RequestFailed -> {
                // AP-22: the batch was never evaluated — every event stays PENDING.
                val n = outbox.applyRequestFailure(sendable, outcome, capabilities, clock())
                DrainResult.RequestFailed(outcome.httpStatus, outcome.retryableAtRequestLevel, n)
            }
            is SendOutcome.Evaluated -> {
                val verdict = verdictParser.parse(outcome.body)
                val byKey = sendable.associateBy { it.deviceId to it.seq }
                val r = outbox.applyVerdict(verdict, byKey, capabilities, ticket.batchId, clock())
                DrainResult.Evaluated(r)
            }
        }
    }

    sealed interface DrainResult {
        data object NothingToSend : DrainResult
        data object NoTransport : DrainResult
        data class RequestFailed(val status: Int?, val retryable: Boolean, val returnedToPending: Int) : DrainResult
        data class Evaluated(val result: OutboxEngine.VerdictResult) : DrainResult
    }

    companion object { const val DEFAULT_BATCH = 50 }
}

/**
 * Turns outbox rows into the opaque bytes a transport carries.
 *
 * M7 provides the JSON form `09` §2.2 specifies for `POST /v1/events`. **The
 * bit-packed wire codec is M8** (`08` Parts 9–10, AD-07), and so are
 * `base_seq`/`base_t` framing and the truncated MAC. This interface is the seam
 * where M8 will register its encoder without the sync layer changing.
 */
interface BatchEncoder {
    /** Trims a candidate list to what fits a transport's declared byte budget. */
    fun fit(rows: List<OutboxRow>, maxBatchBytes: Int): List<OutboxRow>
    suspend fun encode(rows: List<OutboxRow>, db: FieldDatabase): ByteArray
}

/** Parses the opaque `200` body into a [BatchVerdict] (`09` §2.3). */
interface VerdictParser {
    fun parse(body: ByteArray): BatchVerdict
}
