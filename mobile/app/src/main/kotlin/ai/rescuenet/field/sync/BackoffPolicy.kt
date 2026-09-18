package ai.rescuenet.field.sync

import ai.rescuenet.field.domain.Priority
import ai.rescuenet.field.transport.CostClass
import ai.rescuenet.field.transport.LatencyClass
import ai.rescuenet.field.transport.TransportCapabilities
import kotlin.math.min
import kotlin.random.Random

/**
 * Retry backoff — **`08` §6.3 and §6.3.1 (DM-56)**.
 *
 * `delay = min(base × 2^attempt, cap)` with **±20% jitter**.
 *
 * | Transport | Priority | Base | Cap |
 * |---|---|---|---|
 * | Internet | `ROUTINE`  | 2 s  | 5 min |
 * | Internet | `CRITICAL` | 1 s  | 60 s  |
 * | SMS      | `ROUTINE`  | 60 s | 30 min |
 * | SMS      | `CRITICAL` | 10 s | 5 min |
 *
 * There is deliberately **no `RETRY` state**: retry is `PENDING` with a future
 * `next_attempt_at` (DM-16). Backoff governs `PENDING` rows only — a `REJECTED`
 * row is never retried at all (`09` §2.7.5).
 *
 * The transport tier is read from **declared capabilities**, never from a
 * transport's name or class (AD-08). "SMS-like" here means METERED and
 * VERY_SLOW, which is exactly how `06` §7.3 and AD-09 describe that path.
 */
object BackoffPolicy {

    data class Bounds(val baseMs: Long, val capMs: Long)

    val INTERNET_ROUTINE  = Bounds(2_000L, 5 * 60_000L)
    val INTERNET_CRITICAL = Bounds(1_000L, 60_000L)
    val SMS_ROUTINE       = Bounds(60_000L, 30 * 60_000L)
    val SMS_CRITICAL      = Bounds(10_000L, 5 * 60_000L)

    const val JITTER_FRACTION = 0.20

    fun bounds(capabilities: TransportCapabilities, priority: Priority): Bounds {
        val metered = capabilities.costClass == CostClass.METERED &&
            capabilities.latencyClass == LatencyClass.VERY_SLOW
        return when {
            metered && priority == Priority.CRITICAL -> SMS_CRITICAL
            metered -> SMS_ROUTINE
            priority == Priority.CRITICAL -> INTERNET_CRITICAL
            else -> INTERNET_ROUTINE
        }
    }

    /** Undelayed, unjittered delay for attempt `n` (0-based). Exposed for testing bounds. */
    fun rawDelayMs(bounds: Bounds, attempt: Int): Long {
        if (attempt >= 62) return bounds.capMs          // 2^attempt would overflow Long
        val scaled = bounds.baseMs shl attempt          // base × 2^attempt
        return if (scaled < 0) bounds.capMs else min(scaled, bounds.capMs)
    }

    /** Applies ±20% jitter. Never returns a negative delay. */
    fun delayMs(bounds: Bounds, attempt: Int, random: Random = Random.Default): Long {
        val raw = rawDelayMs(bounds, attempt)
        val jitter = (raw * JITTER_FRACTION * (random.nextDouble() * 2.0 - 1.0)).toLong()
        return (raw + jitter).coerceAtLeast(0L)
    }

    fun nextAttemptAt(
        now: Long,
        capabilities: TransportCapabilities,
        priority: Priority,
        attempt: Int,
        random: Random = Random.Default,
    ): Long = now + delayMs(bounds(capabilities, priority), attempt, random)
}
