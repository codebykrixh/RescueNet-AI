"""SMS wire codec — the Python side.

Mirrors ``mobile/app/src/main/kotlin/ai/rescuenet/field/codec`` exactly, because
the batch MAC covers **packed wire bytes** (DM-49): the gateway forwards decoded
JSON, so the backend must re-pack the events bit-for-bit to recompute the MAC.

Every width comes from the ratified wire format, ``docs/09`` §6.6 / **DM-57**.
"""

from rescuenet.codec.bitio import BitWriter
from rescuenet.codec.mac import compute_mac, verify_mac
from rescuenet.codec.wire import (
    WireEncodingError,
    encode_payload,
    event_bits,
    pack_event,
    pack_header,
)

__all__ = [
    "BitWriter",
    "WireEncodingError",
    "compute_mac",
    "verify_mac",
    "encode_payload",
    "event_bits",
    "pack_event",
    "pack_header",
]
