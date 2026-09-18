"""Gateway batch MAC verification — **TR-10**, ``docs/09`` §6.6.5, AP-16, DM-49.

**This closes DM-51.** Until M8 a ``GATEWAY``-relayed batch had unverified
author authenticity: the gateway's own token authenticates the *relay*, but only
the per-device MAC authenticates the *author*. Without it a compromised gateway
could fabricate events attributed to any team (AP-16).

The gateway forwards **decoded canonical JSON** (``09`` §11.10), while the MAC
covers **packed wire bytes** (DM-49). So the backend re-packs the batch bit-for-
bit using :mod:`rescuenet.codec` — the Python mirror of the device codec, locked
to it by a shared known-answer vector — and recomputes the MAC.

``base_t`` is *seconds since incident start* (``09`` §6.6.1). The backend
reconstructs it from ``INCIDENT_DECLARED.started_at`` in its own event log,
which is the same origin the device caches, so both sides derive the same value
from the same ``t_dev``.

**Framing is not covered** and the ``mac`` field is excluded from its own input
(M8-10). ``FIELD`` batches need no MAC: they arrive over TLS and their
``device_id`` is bound to the authenticated device.
"""

from __future__ import annotations

import binascii
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from rescuenet.codec import WireEncodingError, encode_payload, verify_mac
from rescuenet.domain.enums import EventType
from rescuenet.store.codes import EVENT_TYPE_CODE
from rescuenet.store.tables import device_credential, event


class BatchMacError(Exception):
    """MAC verification failed. The caller must return 401 and persist nothing."""


_CODE_TO_TYPE = {code: t for t, code in EVENT_TYPE_CODE.items()}


def _to_epoch_seconds(value: Any) -> int:
    """Epoch seconds, with **naive timestamps read as UTC**.

    The device performs the identical conversion in ``IncidentEpoch``. That
    agreement is load-bearing: ``base_t`` is derived from this value on both
    sides, and the MAC is computed over a header containing it, so a one-hour
    disagreement would fail every MAC. Reading a naive timestamp as *local* time
    would make the result depend on the reader's timezone — the device's and the
    server's need not match — so UTC is the only interpretation that can be
    shared.
    """
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    if isinstance(value, (int, float)):
        return int(value if value < 10**12 else value / 1000)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())


def incident_started_at(conn: Connection, incident_id: int) -> int | None:
    """Incident start, in epoch seconds, from the authoritative event log."""
    row = conn.execute(
        select(event.c.payload, event.c.t_dev)
        .where(event.c.incident_id == incident_id)
        .where(event.c.type == EVENT_TYPE_CODE[EventType.INCIDENT_DECLARED])
        .order_by(event.c.server_seq)
        .limit(1)
    ).first()
    if row is None:
        return None
    payload = row[0] or {}
    started = payload.get("started_at")
    return _to_epoch_seconds(started if started is not None else row[1])


def _device_secret(conn: Connection, device_id: int) -> bytes | None:
    return conn.execute(
        select(device_credential.c.hmac_secret)
        .where(device_credential.c.device_id == device_id)
    ).scalar_one_or_none()


def verify_gateway_batch(conn: Connection, batch: dict[str, Any], caller: Any) -> None:
    """Verify a relayed batch, or raise :class:`BatchMacError`.

    A no-op for any role other than ``GATEWAY``.
    """
    if caller is None or getattr(caller, "role", None) != "GATEWAY":
        return

    presented_hex = batch.get("mac")
    if not presented_hex:
        raise BatchMacError("a GATEWAY batch must carry a MAC (AP-16)")
    try:
        presented = binascii.unhexlify(presented_hex)
    except (binascii.Error, TypeError) as exc:
        raise BatchMacError("mac is not valid hex") from exc

    events = batch.get("events") or []
    if not events:
        raise BatchMacError("a GATEWAY batch must carry at least one event")

    origin = batch.get("origin_device_id")
    if origin is None:
        origin = events[0].get("device_id")

    secret = _device_secret(conn, origin)
    if not secret:
        raise BatchMacError(f"no hmac_secret enrolled for device {origin}")

    ordered = sorted(events, key=lambda e: e["seq"])
    first = ordered[0]
    incident_id = first["incident_id"]
    started = incident_started_at(conn, incident_id)
    if started is None:
        raise BatchMacError(f"incident {incident_id} has no INCIDENT_DECLARED to anchor base_t")

    base_seq = first["seq"]
    base_t = _to_epoch_seconds(first["t_dev"]) - started
    if base_t < 0:
        raise BatchMacError("base_t is negative: an event predates the incident")

    header = {
        "proto_version": 1,
        "device_id": first["device_id"],
        "team_id": first["team_id"],
        "agency_id": first["agency_id"],
        "incident_id": incident_id,
        "schema_version": first["schema_version"],
        "base_seq": base_seq,
        "base_t": base_t,
        "event_count": len(ordered),
    }

    packed_events = []
    for e in ordered:
        raw_type = e["type"]
        etype = _CODE_TO_TYPE.get(raw_type) if isinstance(raw_type, int) else EventType(raw_type)
        if etype is None:
            raise BatchMacError(f"unknown event type {raw_type!r}")
        packed_events.append({
            "type": etype,
            "seq_delta": e["seq"] - base_seq,
            "t_delta": (_to_epoch_seconds(e["t_dev"]) - started) - base_t,
            "responder_id": e["responder_id"],
            "payload": e["payload"],
        })

    try:
        payload = encode_payload(header, packed_events)
    except (WireEncodingError, ValueError, KeyError) as exc:
        raise BatchMacError(f"batch is not representable on the SMS wire: {exc}") from exc

    if not verify_mac(secret, payload, presented):
        raise BatchMacError("MAC verification failed")
