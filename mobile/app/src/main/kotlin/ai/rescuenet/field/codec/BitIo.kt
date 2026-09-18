package ai.rescuenet.field.codec

/**
 * MSB-first bit writer — `09` §6.6.2 / DM-57.
 *
 * Fields are packed contiguously with no per-field or per-event byte padding.
 * **Only the completed blob is zero-padded to a byte boundary**, once, by
 * [toByteArray].
 */
class BitWriter(initialBytes: Int = 32) {
    private var buf = ByteArray(initialBytes)
    private var bitPos = 0

    val bitLength: Int get() = bitPos
    val byteLength: Int get() = (bitPos + 7) / 8

    /**
     * Appends the low [bits] bits of [value], MSB-first.
     *
     * Refuses a value that does not fit: silently masking it would be
     * truncation, which `08` §10.1 rule 2 forbids.
     */
    fun write(value: Long, bits: Int) {
        require(bits in 1..64) { "bits must be 1..64, was $bits" }
        if (bits < 64) {
            val max = (1L shl bits) - 1
            if (value < 0 || value > max) {
                throw WireEncodingException("value $value does not fit $bits unsigned bits (max $max)")
            }
        }
        ensure(bitPos + bits)
        for (i in bits - 1 downTo 0) {
            if ((value ushr i) and 1L == 1L) {
                buf[bitPos ushr 3] = (buf[bitPos ushr 3].toInt() or (0x80 ushr (bitPos and 7))).toByte()
            }
            bitPos++
        }
    }

    fun write(value: Int, bits: Int) = write(value.toLong(), bits)

    /**
     * Appends a two's-complement signed value in [bits] bits.
     * Range is `-2^(bits-1) .. 2^(bits-1)-1`; anything else is refused.
     */
    fun writeSigned(value: Int, bits: Int) {
        val min = -(1 shl (bits - 1))
        val max = (1 shl (bits - 1)) - 1
        if (value < min || value > max) {
            throw WireEncodingException("signed value $value does not fit $bits bits ($min..$max)")
        }
        write(value.toLong() and ((1L shl bits) - 1), bits)
    }

    private fun ensure(bitsNeeded: Int) {
        val bytesNeeded = (bitsNeeded + 7) / 8
        if (bytesNeeded > buf.size) buf = buf.copyOf(maxOf(bytesNeeded, buf.size * 2))
    }

    /** The completed blob, zero-padded to a byte boundary exactly once. */
    fun toByteArray(): ByteArray = buf.copyOf(byteLength)
}

/** MSB-first bit reader, the exact inverse of [BitWriter]. */
class BitReader(private val buf: ByteArray) {
    private var bitPos = 0

    val bitsRead: Int get() = bitPos
    val bitsRemaining: Int get() = buf.size * 8 - bitPos

    fun read(bits: Int): Long {
        require(bits in 1..64) { "bits must be 1..64, was $bits" }
        if (bits > bitsRemaining) {
            throw WireDecodingException("truncated input: need $bits bits, $bitsRemaining remain")
        }
        var v = 0L
        repeat(bits) {
            val bit = (buf[bitPos ushr 3].toInt() ushr (7 - (bitPos and 7))) and 1
            v = (v shl 1) or bit.toLong()
            bitPos++
        }
        return v
    }

    fun readInt(bits: Int): Int = read(bits).toInt()

    /** Reads [bits] as two's-complement signed. */
    fun readSigned(bits: Int): Int {
        val raw = read(bits)
        val signBit = 1L shl (bits - 1)
        return if (raw and signBit != 0L) (raw - (1L shl bits)).toInt() else raw.toInt()
    }

    /**
     * Verifies that only zero padding remains — an ambiguous encoding with
     * non-zero trailing bits is rejected rather than accepted.
     */
    fun requireOnlyZeroPaddingLeft() {
        if (bitsRemaining >= 8) {
            throw WireDecodingException("$bitsRemaining trailing bits: a whole byte or more is unaccounted for")
        }
        while (bitsRemaining > 0) {
            if (read(1) != 0L) throw WireDecodingException("non-zero padding bit — ambiguous encoding")
        }
    }
}
