"""Credential lookup, enrolment, sessions and join codes (endpoints 1, 2, 6)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Connection, func, insert, select, update

from rescuenet.domain import EventType
from rescuenet.domain.limits import MAX_DEVICE_ID, MIN_ENROLLED_DEVICE_ID
from rescuenet.services import credentials, errors, server_events
from rescuenet.store.tables import (
    device_credential, event as event_table, incident as incident_table, join_code,
)

FIELD, GATEWAY, COMMANDER = "FIELD", "GATEWAY", "COMMANDER"
DEVICE_ROLES = frozenset({FIELD, GATEWAY})

DEFAULT_JOIN_CODE_TTL = timedelta(hours=24)
DEFAULT_JOIN_CODE_MAX_USES = 5

#: DM-53 — placeholder, NOT a real agency. Future contract decision.
PROVISIONAL_AGENCY_ID = 0


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. Never carries a secret."""

    credential_id: int
    role: str
    device_id: int | None
    incident_id: int | None
    team_id: int | None = None
    responder_id: int | None = None
    agency_id: int | None = None

    @property
    def is_commander(self) -> bool:
        return self.role == COMMANDER

    @property
    def is_device(self) -> bool:
        return self.role in DEVICE_ROLES


def _device_enrolment(conn: Connection, device_id: int):
    """A device's incident/team/responder, from its DEVICE_ENROLLED event.

    The event log is the source of truth; the credential row does not duplicate
    this (docs/08 §11.1b).
    """
    from rescuenet.store.codes import EVENT_TYPE_CODE

    row = conn.execute(
        select(event_table.c.incident_id, event_table.c.payload)
        .where(event_table.c.type == EVENT_TYPE_CODE[EventType.DEVICE_ENROLLED])
        .order_by(event_table.c.server_seq.desc())
    ).mappings().all()
    for r in row:
        if r["payload"].get("device_id") == device_id:
            return r["incident_id"], r["payload"].get("team_id"), r["payload"].get("responder_id")
    return None, None, None


def resolve_token(conn: Connection, token: str) -> Principal:
    """Authenticate a bearer token, or raise the documented 401."""
    row = conn.execute(
        select(device_credential).where(
            device_credential.c.token_hash == credentials.hash_token(token))
    ).mappings().one_or_none()

    if row is None:
        raise errors.ApiError(401, "UNAUTHENTICATED", "invalid token")
    if row["revoked_at"] is not None:
        raise errors.ApiError(401, "TOKEN_REVOKED", "credential has been revoked")
    if row["role"] == COMMANDER and credentials.is_expired(row["issued_at"]):
        raise errors.ApiError(401, "SESSION_EXPIRED", "session has expired")

    incident_id, team_id, responder_id = row["incident_id"], None, None
    if row["role"] in DEVICE_ROLES and row["device_id"] is not None:
        incident_id, team_id, responder_id = _device_enrolment(conn, row["device_id"])

    return Principal(
        credential_id=row["credential_id"], role=row["role"],
        device_id=row["device_id"], incident_id=incident_id,
        team_id=team_id, responder_id=responder_id,
    )


def _next_device_id(conn: Connection) -> int:
    highest = conn.execute(
        select(func.coalesce(func.max(device_credential.c.device_id), 0))
    ).scalar_one()
    nxt = max(highest + 1, MIN_ENROLLED_DEVICE_ID)
    if nxt > MAX_DEVICE_ID:
        raise errors.conflict("DEVICE_SPACE_EXHAUSTED",
                              f"no device_id available below {MAX_DEVICE_ID}")
    return nxt


def mint_join_code(conn: Connection, team_id: int, incident_id: int,
                   max_uses: int = DEFAULT_JOIN_CODE_MAX_USES) -> dict:
    """Endpoint 6 — mint a join code (DM-45)."""
    if conn.execute(select(incident_table.c.incident_id).where(
            incident_table.c.incident_id == incident_id)).scalar_one_or_none() is None:
        raise errors.not_found("UNKNOWN_INCIDENT", f"incident {incident_id} does not exist")

    expires_at = datetime.now(timezone.utc) + DEFAULT_JOIN_CODE_TTL
    code = credentials.new_join_code()
    conn.execute(insert(join_code).values(
        code=code, team_id=team_id, incident_id=incident_id,
        expires_at=expires_at, max_uses=max_uses, uses=0))
    return {"join_code": code, "expires_at": expires_at.isoformat(),
            "max_uses": max_uses}


def enrol(conn: Connection, code: str, mode: str, label: str | None) -> dict:
    """Endpoint 1 — enrol a device.

    **Deliberately non-idempotent** (AP-02, TR-33): two enrolments with one code
    yield two distinct ``device_id`` values, because two physical handsets must
    never share an identity.
    """
    if mode not in DEVICE_ROLES:
        raise errors.unprocessable("INVALID_MODE", "mode must be FIELD or GATEWAY")

    row = conn.execute(
        select(join_code).where(join_code.c.code == code.strip().upper())
    ).mappings().one_or_none()
    if row is None:
        raise errors.not_found("UNKNOWN_JOIN_CODE", "join code not recognised")

    expires_at = row["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) >= expires_at:
        raise errors.conflict("JOIN_CODE_EXPIRED", "join code has expired")
    if row["uses"] >= row["max_uses"]:
        raise errors.conflict("JOIN_CODE_EXHAUSTED", "join code has no uses left")

    device_id = _next_device_id(conn)
    token = credentials.new_token()
    secret = credentials.new_hmac_secret()

    conn.execute(insert(device_credential).values(
        device_id=device_id, token_hash=credentials.hash_token(token),
        hmac_secret=secret, role=mode, incident_id=None))
    conn.execute(update(join_code)
                 .where(join_code.c.code == row["code"])
                 .values(uses=row["uses"] + 1))

    # DM-53 — PROVISIONAL DEFAULTS, not settled contract. `09` endpoint 1 returns
    # `responder_id` and `agency_id` but no document specifies their source; the
    # join code carries only team_id and incident_id. `agency_id = 0` is a
    # placeholder and is NOT a real agency. See docs/08 §11.1d.
    responder_id = device_id
    payload = {"device_id": device_id, "team_id": row["team_id"],
               "responder_id": responder_id}
    if label is not None:
        payload["label"] = label
    _, result = server_events.author(
        conn, event_type=EventType.DEVICE_ENROLLED, entity_id=device_id,
        payload=payload, incident_id=row["incident_id"])

    import base64

    return {
        "device_id": device_id, "token": token,
        "hmac_secret": base64.b64encode(secret).decode(),
        "incident_id": row["incident_id"], "team_id": row["team_id"],
        "agency_id": PROVISIONAL_AGENCY_ID, "responder_id": responder_id,
        "server_seq": result.server_seq, "role": mode,
    }


def open_session(conn: Connection, incident_id: int, password: str,
                 mqtt_block: dict | None) -> dict:
    """Endpoint 2 — commander login (DM-46, DM-48, DM-50)."""
    row = conn.execute(
        select(incident_table.c.password_hash).where(
            incident_table.c.incident_id == incident_id)
    ).mappings().one_or_none()
    if row is None:
        raise errors.not_found("UNKNOWN_INCIDENT", f"incident {incident_id} does not exist")
    if not credentials.verify_password(password, row["password_hash"]):
        raise errors.ApiError(401, "UNAUTHENTICATED", "incident password is incorrect")

    token = credentials.new_token()
    issued_at = datetime.now(timezone.utc)
    conn.execute(insert(device_credential).values(
        device_id=None, token_hash=credentials.hash_token(token),
        hmac_secret=None, role=COMMANDER, incident_id=incident_id,
        issued_at=issued_at))

    body = {"token": token,
            "expires_at": credentials.session_expires_at(issued_at).isoformat(),
            "role": COMMANDER, "incident_id": incident_id}
    if mqtt_block:
        body["mqtt"] = mqtt_block
    return body


def set_incident_password(conn: Connection, incident_id: int, password: str) -> None:
    """Store the scrypt hash. The plaintext is never persisted (DM-48)."""
    conn.execute(update(incident_table)
                 .where(incident_table.c.incident_id == incident_id)
                 .values(password_hash=credentials.hash_password(password)))
