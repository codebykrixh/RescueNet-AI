package ai.rescuenet.field.sync

/**
 * The parsed `200` ingestion response — `09` §2.3.
 *
 * ```json
 * { "accepted": [ { "device_id":17, "seq":4021, "server_seq":1201, "was_duplicate":false } ],
 *   "rejected": [ { "device_id":17, "seq":4025, "code":"UNKNOWN_CELL",
 *                   "retryable":false, "message":"…" } ],
 *   "server_seq_high": 1203 }
 * ```
 *
 * **Duplicates arrive in `accepted` with `was_duplicate: true`, never in
 * `rejected`** (AP-05, AD-28). The client's correct action is identical either
 * way — mark it `ACKED` — so the flag is diagnostics only.
 */
data class BatchVerdict(
    val accepted: List<AcceptedEvent>,
    val rejected: List<RejectedEvent>,
    val serverSeqHigh: Long?,
)

data class AcceptedEvent(
    val deviceId: Int,
    val seq: Long,
    val serverSeq: Long?,
    val wasDuplicate: Boolean,
)

/**
 * One per-event rejection.
 *
 * **[retryable] is the only field that decides the outbox transition.**
 * `09` §2.6.1 / **AP-21**: *"The client acts on the `retryable` boolean and
 * never interprets the `code` string."* [code] and [message] are diagnostics,
 * stored for the operator and never branched on. That is what lets the server
 * introduce a new rejection code without a client release.
 */
data class RejectedEvent(
    val deviceId: Int,
    val seq: Long,
    val code: String,
    val retryable: Boolean,
    val message: String?,
)
