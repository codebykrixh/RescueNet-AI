package ai.rescuenet.field.codec

import ai.rescuenet.field.domain.EventType

/**
 * Payload enums for the four SMS-eligible types, with wire codes taken from the
 * declaration order in `08` §2.2 and mirroring
 * `backend/src/rescuenet/domain/enums.py`.
 *
 * These are **wire codes**: like the `type` codes of `08` §14.1 they are
 * positional and must not be renumbered.
 */
enum class CellStatus(val code: Int) {
    IN_PROGRESS(0), SEARCHED(1), NEEDS_RESEARCH(2);
    companion object { fun of(c: Int) = entries.firstOrNull { it.code == c }
        ?: throw WireDecodingException("unknown cell status code $c") }
}

enum class SurvivorStatus(val code: Int) {
    TRAPPED(0), ACCESSIBLE(1), EXTRICATED(2), DECEASED(3);
    companion object { fun of(c: Int) = entries.firstOrNull { it.code == c }
        ?: throw WireDecodingException("unknown survivor status code $c") }
}

/** **Not clinically validated** — `05` AL-08 requires this stated wherever triage appears. */
enum class Triage(val code: Int) {
    RED(0), YELLOW(1), GREEN(2), BLACK(3);
    companion object { fun of(c: Int) = entries.firstOrNull { it.code == c }
        ?: throw WireDecodingException("unknown triage code $c") }
}

enum class TeamStatus(val code: Int) {
    ACTIVE(0), STANDBY(1), OUT_OF_SERVICE(2);
    companion object { fun of(c: Int) = entries.firstOrNull { it.code == c }
        ?: throw WireDecodingException("unknown team status code $c") }
}

/**
 * The four SMS-eligible uplink event types — **SCOPE A**, `09` §6.6.2 / M8-6.
 *
 * The seven other canonical types have **no SMS layout and must not be given
 * one**. They travel the JSON/HTTPS path, which already carries all eleven
 * losslessly. `POSITION_REPORTED` is **never** sent over SMS (M8-7).
 */
sealed interface WireEvent {
    val seqDelta: Int
    val tDelta: Int
    val responderId: Int
    val type: EventType

    data class CellStatusReported(
        override val seqDelta: Int, override val tDelta: Int,
        val cellIndex: Int, val status: CellStatus, override val responderId: Int,
    ) : WireEvent { override val type get() = EventType.CELL_STATUS_REPORTED }

    data class ResourceDeltaReported(
        override val seqDelta: Int, override val tDelta: Int,
        val itemId: Int, val qtyDelta: Int, override val responderId: Int,
    ) : WireEvent { override val type get() = EventType.RESOURCE_DELTA_REPORTED }

    data class TeamStatusReported(
        override val seqDelta: Int, override val tDelta: Int,
        val teamStatus: TeamStatus, override val responderId: Int,
    ) : WireEvent { override val type get() = EventType.TEAM_STATUS_REPORTED }

    /** `note` is never transmitted over SMS (`08` Part 9) and is absent by construction. */
    data class SurvivorReported(
        override val seqDelta: Int, override val tDelta: Int,
        val cellIndex: Int, val personCount: Int, val survivorStatus: SurvivorStatus,
        val triage: Triage?, val relLat: Int?, val relLon: Int?,
        override val responderId: Int,
    ) : WireEvent { override val type get() = EventType.SURVIVOR_REPORTED }
}

/** The nine-field batch header — `09` §6.6.1. 89 bits. */
data class BatchHeader(
    val protoVersion: Int = WireLimits.PROTO_VERSION,
    val deviceId: Int,
    val teamId: Int,
    val agencyId: Int,
    val incidentId: Int,
    val schemaVersion: Int,
    val baseSeq: Long,
    /** Unsigned seconds since incident start. */
    val baseT: Long,
    val eventCount: Int,
)

/** Framing — `09` §6.6.4. Level 1 is single-segment, so part index/total are 1/1. */
data class Framing(
    val batchId: Int,
    val partIndex: Int = 1,
    val partTotal: Int = 1,
    val originDeviceId: Int,
    /** 4 bytes. Computed over header ‖ events only (`09` §6.6.5). */
    val mac: ByteArray,
) {
    override fun equals(other: Any?) = this === other || (other is Framing &&
        batchId == other.batchId && partIndex == other.partIndex &&
        partTotal == other.partTotal && originDeviceId == other.originDeviceId &&
        mac.contentEquals(other.mac))
    override fun hashCode() = (((batchId * 31 + partIndex) * 31 + partTotal) * 31 +
        originDeviceId) * 31 + mac.contentHashCode()
}

/** A complete decoded SMS batch. */
data class WireBatch(val framing: Framing, val header: BatchHeader, val events: List<WireEvent>)

/** The 3-byte downlink ACK — `09` §6.6.6. */
data class SmsAck(
    val protoVersion: Int = WireLimits.ACK_PROTO_VERSION,
    val highestContiguousSeq: Long,
)
