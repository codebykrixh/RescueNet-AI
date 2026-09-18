"""MSB-first bit writer — the exact counterpart of the Kotlin ``BitWriter``.

``docs/09`` §6.6.2: fields are packed contiguously, MSB-first, with no per-field
or per-event padding. Only the completed blob is zero-padded to a byte boundary,
once.
"""

from __future__ import annotations


class BitWriter:
    """Accumulates bits MSB-first. Refuses any value that does not fit."""

    __slots__ = ("_bits",)

    def __init__(self) -> None:
        self._bits: list[int] = []

    def write(self, value: int, bits: int) -> None:
        """Append the low ``bits`` bits of ``value``.

        Masking an over-wide value would be truncation, which ``08`` §10.1
        rule 2 forbids, so it raises instead.
        """
        if bits < 1:
            raise ValueError(f"bits must be >= 1, got {bits}")
        top = (1 << bits) - 1
        if value < 0 or value > top:
            raise ValueError(f"value {value} does not fit {bits} unsigned bits (max {top})")
        for i in range(bits - 1, -1, -1):
            self._bits.append((value >> i) & 1)

    def write_signed(self, value: int, bits: int) -> None:
        """Append a two's-complement signed value."""
        low, high = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
        if value < low or value > high:
            raise ValueError(f"signed value {value} does not fit {bits} bits ({low}..{high})")
        self.write(value & ((1 << bits) - 1), bits)

    @property
    def bit_length(self) -> int:
        return len(self._bits)

    def to_bytes(self) -> bytes:
        """The blob, zero-padded to a byte boundary exactly once."""
        out = bytearray((len(self._bits) + 7) // 8)
        for i, bit in enumerate(self._bits):
            if bit:
                out[i >> 3] |= 0x80 >> (i & 7)
        return bytes(out)
