package ai.rescuenet.field.codec

import ai.rescuenet.field.codec.WireLimits as L

/**
 * The compact downlink ACK — **`09` §6.6.6, §6.4, D-06**.
 *
 * ```
 * ack_proto              4 bits
 * highest_contiguous_seq 20 bits          => 24 bits = 3 bytes
 * ```
 *
 * **Unauthenticated and carrying no `device_id`**, exactly as ratified (M8-11).
 * The ACK is delivered to the device's own SMS address, so identity would spend
 * wire bytes restating what the channel already establishes; and no document
 * requires downlink authentication. A forged ACK can only cause a redundant
 * re-send, which the server de-duplicates by `(device_id, seq)`.
 *
 * §6.4's trade, stated: if 4021, 4022 and 4024 are accepted the ACK carries
 * **4022**. The device re-sends 4024 and the server de-duplicates it. One
 * redundant transmission buys a fixed-size ACK on a throttle-constrained
 * downlink (TL-4).
 */
object AckCodec {

    fun encode(ack: SmsAck): ByteArray {
        if (ack.protoVersion !in 0..15) {
            throw WireEncodingException("ack_proto ${ack.protoVersion} out of range 0..15")
        }
        if (ack.highestContiguousSeq !in 0..L.MAX_SEQ) {
            throw WireEncodingException(
                "highest_contiguous_seq ${ack.highestContiguousSeq} exceeds the 20-bit range 0..${L.MAX_SEQ}"
            )
        }
        val w = BitWriter(L.ACK_BYTES)
        w.write(ack.protoVersion, L.ACK_PROTO_BITS)
        w.write(ack.highestContiguousSeq, L.ACK_SEQ_BITS)
        return w.toByteArray()
    }

    fun decode(bytes: ByteArray): SmsAck {
        if (bytes.size != L.ACK_BYTES) {
            throw WireDecodingException("ACK must be exactly ${L.ACK_BYTES} bytes, got ${bytes.size}")
        }
        val r = BitReader(bytes)
        val proto = r.readInt(L.ACK_PROTO_BITS)
        if (proto != L.ACK_PROTO_VERSION) throw WireDecodingException("unsupported ack_proto $proto")
        return SmsAck(proto, r.read(L.ACK_SEQ_BITS))
    }

    /**
     * Monotonic application — `09` §6.6.6.
     *
     * A value lower than or equal to the current watermark is a **no-op**, so
     * replays and duplicates are harmless. Only a strictly higher contiguous
     * sequence advances acknowledgement.
     *
     * @return the watermark after applying [ack].
     */
    fun advance(current: Long, ack: SmsAck): Long =
        if (ack.highestContiguousSeq > current) ack.highestContiguousSeq else current
}
