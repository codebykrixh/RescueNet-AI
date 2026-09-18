"""Batch MAC verification — ``docs/09`` §6.6.5, **AD-24**, **AP-16**, **DM-49**.

::

    mac = HMAC-SHA256(hmac_secret, header || packed_events)[0:4]

Framing is **not** covered, and the ``mac`` field is excluded from its own
input. That is exactly the ratified boundary (M8-10): DM-23 requires header
coverage, AP-16 requires authorship coverage, and TR-10 requires rejection of a
tampered *payload* — it says nothing about framing, which is M9's reassembly
metadata.

**This closes DM-51.** Until now a `GATEWAY`-relayed batch had unverified author
authenticity: the gateway's own token authenticates the relay, but only the
per-device MAC authenticates the author (AP-16).
"""

from __future__ import annotations

import hmac
from hashlib import sha256
from typing import Final

MAC_BYTES: Final = 4


def compute_mac(secret: bytes, payload: bytes) -> bytes:
    """The leading 4 bytes of HMAC-SHA256 over ``header || packed_events``."""
    if not secret:
        raise ValueError("hmac_secret must not be empty")
    return hmac.new(secret, payload, sha256).digest()[:MAC_BYTES]


def verify_mac(secret: bytes, payload: bytes, presented: bytes) -> bool:
    """Constant-time comparison of a presented 4-byte MAC."""
    if presented is None or len(presented) != MAC_BYTES:
        return False
    return hmac.compare_digest(compute_mac(secret, payload), presented)
