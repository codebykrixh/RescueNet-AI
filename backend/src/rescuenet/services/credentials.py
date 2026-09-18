"""Credential issuance, hashing and verification (docs/08 §11.1a–c, M5).

Secrets discipline for this module:
  * plaintext passwords are never persisted;
  * bearer tokens are persisted only as ``SHA-256`` (DM-43);
  * ``hmac_secret`` is stored **recoverably** because M8 must recompute MACs
    with it (DM-47) — it is returned exactly once, at enrolment;
  * nothing here is ever logged or printed.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# ── tokens (DM-43) ──────────────────────────────────────────────────────────
#: 32 CSPRNG bytes -> 43 URL-safe base64 characters, ~256 bits.
TOKEN_BYTES = 32

# ── join codes (DM-45) ──────────────────────────────────────────────────────
#: 31 symbols, excluding I, L, O, 0, 1 — typed under stress, spoken over radio.
JOIN_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
JOIN_CODE_LENGTH = 6

# ── sessions (DM-46) ────────────────────────────────────────────────────────
SESSION_TTL = timedelta(hours=24)

# ── scrypt password hashing (DM-48) ─────────────────────────────────────────
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
SALT_BYTES = 16

HMAC_SECRET_BYTES = 32


def new_token() -> str:
    """A fresh opaque bearer token. Returned once; never persisted in the clear."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    """``SHA-256(token)`` as hex (DM-43).

    A fast one-way hash is correct here and wrong for passwords: the input is
    256 bits of uniform entropy, so there is nothing to brute-force.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_join_code() -> str:
    """A cryptographically random join code (DM-45)."""
    return "".join(secrets.choice(JOIN_CODE_ALPHABET) for _ in range(JOIN_CODE_LENGTH))


def new_hmac_secret() -> bytes:
    """Per-device HMAC secret. Stored recoverably (DM-47); never logged."""
    return secrets.token_bytes(HMAC_SECRET_BYTES)


def hash_password(password: str) -> str:
    """Derive ``scrypt$n=..,r=..,p=..$salt$hash`` with a fresh random salt (DM-48)."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt,
        n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_DKLEN,
    )
    return "$".join((
        "scrypt",
        f"n={SCRYPT_N},r={SCRYPT_R},p={SCRYPT_P}",
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    ))


def verify_password(password: str, stored: str | None) -> bool:
    """Constant-time verification against a stored scrypt representation.

    Returns ``False`` for a missing or malformed hash rather than raising, so a
    caller cannot distinguish "no password set" from "wrong password".
    """
    if not stored:
        return False
    try:
        scheme, params, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        parsed = dict(kv.split("=") for kv in params.split(","))
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt_b64),
            n=int(parsed["n"]), r=int(parsed["r"]), p=int(parsed["p"]),
            dklen=len(base64.b64decode(hash_b64)),
        )
    except (ValueError, KeyError, TypeError):
        return False
    return hmac.compare_digest(digest, base64.b64decode(hash_b64))


def session_expires_at(issued_at: datetime) -> datetime:
    """Derived expiry — there is no ``expires_at`` column (DM-46)."""
    return issued_at + SESSION_TTL


def is_expired(issued_at: datetime, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    return now >= session_expires_at(issued_at)


@dataclass(frozen=True)
class IssuedCredential:
    """What enrolment hands back. ``token`` and ``hmac_secret`` are shown once."""

    credential_id: int
    device_id: int | None
    role: str
    token: str
    hmac_secret: bytes | None
    incident_id: int | None
