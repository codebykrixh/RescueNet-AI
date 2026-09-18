package ai.rescuenet.field

import ai.rescuenet.field.codec.IncidentEpoch
import org.junit.Assert.*
import org.junit.Test

/**
 * `base_t` determinism — `09` §6.6.1.
 *
 * The device and the backend both derive the incident epoch from the *same*
 * `INCIDENT_DECLARED.started_at` string. The MAC is computed over a header
 * containing `base_t`, so any disagreement between the two parsers would fail
 * every MAC. These assert the exact values the backend's
 * ``test_incident_epoch_naive_timestamps_are_read_as_utc`` asserts.
 */
class IncidentEpochTest {

    /** 2026-08-22T09:00:00Z, the value the backend test pins. */
    private val expected = 1787389200L

    @Test fun offsetAwareFormsParseToTheContractValue() {
        assertEquals(expected, IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00+00:00"))
        assertEquals(expected, IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00Z"))
    }

    /**
     * A naive timestamp must be read as **UTC**, never local. Reading it as
     * local would make `base_t` depend on the reader's timezone — and the
     * device's need not match the server's.
     */
    @Test fun naiveTimestampIsReadAsUtcNotLocalTime() {
        assertEquals(expected, IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00"))
    }

    @Test fun allThreeFormsAgree() {
        val forms = listOf(
            "2026-08-22T09:00:00+00:00", "2026-08-22T09:00:00Z", "2026-08-22T09:00:00")
        val results = forms.map { IncidentEpoch.parseEpochSeconds(it) }.toSet()
        assertEquals("all forms must agree: $results", 1, results.size)
        assertEquals(expected, results.first())
    }

    @Test fun nonZeroOffsetsAreHonoured() {
        // 09:00+05:30 is 03:30Z — 5.5 h earlier in epoch terms.
        assertEquals(expected - (5 * 3600 + 1800),
            IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00+05:30"))
    }

    @Test fun epochNumbersAreAccepted() {
        assertEquals(expected, IncidentEpoch.parseEpochSeconds("1787389200"))
        assertEquals(expected, IncidentEpoch.parseEpochSeconds("1787389200000"))
    }

    @Test fun unparseableInputYieldsNullRatherThanAGuess() {
        assertNull(IncidentEpoch.parseEpochSeconds("not a timestamp"))
        assertNull(IncidentEpoch.parseEpochSeconds(""))
    }

    /** Parsing is pure: the same string always yields the same epoch. */
    @Test fun parsingIsDeterministic() {
        repeat(50) {
            assertEquals(expected, IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00Z"))
        }
    }

    /**
     * base_t = (event t_dev seconds) - incident epoch. Derived, never sampled
     * from the wall clock at send time.
     */
    @Test fun baseTIsDerivedFromStoredValuesNotTheWallClock() {
        val epoch = IncidentEpoch.parseEpochSeconds("2026-08-22T09:00:00Z")!!
        val tDevMillis = 1_787_392_800_000L          // 10:00:00Z, one hour later
        assertEquals(3600L, (tDevMillis / 1000) - epoch)
    }
}
