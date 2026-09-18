package ai.rescuenet.field.codec

import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/**
 * The truncated batch MAC — **`09` §6.6.5, AD-24, DM-03, AP-16**.
 *
 * ```
 * mac = HMAC-SHA256(hmac_secret, header ‖ packed_events)[0:4]
 * ```
 *
 * **Framing is not covered**, and the `mac` field is excluded from its own
 * input. That is precisely what the contract requires and no more: DM-23
 * requires the header be covered, AP-16 requires authorship be covered (header
 * attribution plus per-event `responder_id`), and **TR-10 requires rejection of
 * a tampered *payload*** — it does not mention framing. `batch_id`,
 * `part_index` and `part_total` are reassembly metadata owned by **M9**.
 *
 * One MAC per **batch**, never per event (DM-03). **Integrity and authenticity
 * only — no confidentiality** (`06` §14, AD-24): a truncated MAC resists casual
 * forgery, not a determined attacker, and SMS content is visible to the carrier.
 *
 * The secret comes from M6's existing
 * [ai.rescuenet.field.store.DeviceCredentialStore]. **No second credential
 * store and no second crypto implementation exists.**
 */
object BatchMac {

    private const val ALGORITHM = "HmacSHA256"

    /** Full 32-byte HMAC over the payload. Exposed for testing the truncation rule. */
    fun full(secret: ByteArray, payload: ByteArray): ByteArray {
        require(secret.isNotEmpty()) { "hmac_secret must not be empty" }
        val mac = Mac.getInstance(ALGORITHM)
        mac.init(SecretKeySpec(secret, ALGORITHM))
        return mac.doFinal(payload)
    }

    /** The leading 4 bytes, which is what travels on the wire. */
    fun compute(secret: ByteArray, payload: ByteArray): ByteArray =
        full(secret, payload).copyOf(WireLimits.MAC_BYTES)

    /**
     * Constant-time comparison. A byte-by-byte early exit would leak how much of
     * a forged MAC was correct.
     */
    fun verify(secret: ByteArray, payload: ByteArray, presented: ByteArray): Boolean {
        if (presented.size != WireLimits.MAC_BYTES) return false
        val expected = compute(secret, payload)
        var diff = 0
        for (i in expected.indices) diff = diff or (expected[i].toInt() xor presented[i].toInt())
        return diff == 0
    }
}
