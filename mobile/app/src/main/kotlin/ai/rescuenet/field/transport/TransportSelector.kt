package ai.rescuenet.field.transport

import ai.rescuenet.field.domain.Priority

/**
 * Transport selection — **`06` §7.3**, a fixed rule over `capabilities()`:
 *
 *  1. Prefer `available && cost_class == FREE && latency_class == FAST`.
 *  2. Otherwise the highest-capability available transport, subject to
 *     priority: **`ROUTINE` events are not sent over a `METERED`, `VERY_SLOW`
 *     transport** (**AD-09**). Only `CRITICAL` uses that path.
 *  3. If nothing is available, remain `PENDING`.
 *
 * **No rule reads a transport's name or class.** `06` §7.1 forbids it and AD-08
 * depends on it: adding `PeerTransport` at Level 2 must mean registering one
 * more implementation and changing nothing here. Selection is likewise blind to
 * the *event type* — it sees only the [Priority] tier that `08` §1.2 derives
 * from the type (DM-02).
 */
class TransportSelector(private val transports: List<Transport>) {

    fun select(priority: Priority): Transport? {
        val available = transports.filter { it.capabilities().available }

        available.firstOrNull {
            val c = it.capabilities()
            c.costClass == CostClass.FREE && c.latencyClass == LatencyClass.FAST
        }?.let { return it }

        // Rule 2. AD-09: ROUTINE never rides a METERED VERY_SLOW link.
        return available
            .filterNot { priority == Priority.ROUTINE && it.isMeteredAndVerySlow() }
            .maxByOrNull { it.rank() }
    }

    private fun Transport.isMeteredAndVerySlow(): Boolean = capabilities().let {
        it.costClass == CostClass.METERED && it.latencyClass == LatencyClass.VERY_SLOW
    }

    /** "Highest capability" expressed only in declared terms — never type. */
    private fun Transport.rank(): Int = capabilities().let { c ->
        var r = 0
        if (c.costClass == CostClass.FREE) r += 4
        r += when (c.latencyClass) {
            LatencyClass.FAST -> 3
            LatencyClass.SLOW -> 2
            LatencyClass.VERY_SLOW -> 1
        }
        if (c.supportsDownlink) r += 1
        r
    }
}
