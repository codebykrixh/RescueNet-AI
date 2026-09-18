"""**TR-10** — batch MAC verification. Level I, pytest.

Owned by M8 (**DM-49**): the MAC covers packed wire bytes, so it needs the M8
codec. M5 issued and stored the ``hmac_secret`` this verifies against.

``docs/11`` TR-10: *"Valid MAC → accepted. Tampered payload, wrong secret, or
missing MAC on a `GATEWAY` batch → 401, zero events persisted."*

**This closes DM-51**, the transitional gap in which a relayed batch had
unverified author authenticity (AP-16).
"""

from __future__ import annotations

import binascii
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from rescuenet.codec import compute_mac, encode_payload
from rescuenet.domain.enums import EventType
from rescuenet.store.codes import EVENT_TYPE_CODE
from rescuenet.store.tables import device_credential, event

INCIDENT_START = datetime(2026, 8, 22, 9, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def gateway(api, incident, anon_api, owner_engine):
    """An enrolled GATEWAY device, plus the FIELD device whose events it relays."""
    code = api.post(f"/v1/teams/3/join-code",
                    json={"incident_id": incident, "max_uses": 5}).json()["join_code"]
    gw = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "GATEWAY"}).json()
    fd = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"}).json()

    # An INCIDENT_DECLARED anchors base_t (09 §6.6.1).
    with owner_engine.begin() as conn:
        # The append-only grant (DM-29) means only rescuenet_app may INSERT into
        # `event`. RESET ROLE afterwards is essential: this connection returns to
        # the pool, and leaving it as rescuenet_app breaks the next test's
        # TRUNCATE, which needs owner rights.
        conn.execute(text("SET ROLE rescuenet_app"))
        # device_id 0 is the server identity (DM-36); enrolment already used
        # low seq values, so this anchor takes a distinct one.
        conn.execute(event.insert().values(
            device_id=0, seq=999_999, incident_id=incident,
            type=EVENT_TYPE_CODE[EventType.INCIDENT_DECLARED], entity_type=5,
            entity_id=incident,
            payload={"name": "T", "disaster_type": "LANDSLIDE", "origin_lat": 1.0,
                     "origin_lon": 1.0, "started_at": INCIDENT_START.isoformat()},
            t_dev=INCIDENT_START, schema_version=1, responder_id=1,
            team_id=0, agency_id=0,
        ))
        conn.execute(text("RESET ROLE"))
        secret = conn.execute(
            select(device_credential.c.hmac_secret)
            .where(device_credential.c.device_id == fd["device_id"])
        ).scalar_one()
    return gw, fd, bytes(secret)


def _events(fd, incident, n=1):
    out = []
    for i in range(n):
        out.append({
            "device_id": fd["device_id"], "seq": 4021 + i,
            "type": "CELL_STATUS_REPORTED", "entity_type": "CELL", "entity_id": 214,
            "payload": {"cell_index": 214, "status": "SEARCHED"},
            "t_dev": datetime(2026, 8, 22, 10, 0, i, tzinfo=timezone.utc).isoformat(),
            "responder_id": fd["responder_id"], "team_id": fd["team_id"],
            "agency_id": fd.get("agency_id", 0), "incident_id": incident,
            "schema_version": 1,
        })
    return out


def _mac_for(evts, fd, incident, secret):
    base_seq = evts[0]["seq"]
    base_t = int(datetime.fromisoformat(evts[0]["t_dev"]).timestamp()) - int(INCIDENT_START.timestamp())
    header = {
        "proto_version": 1, "device_id": fd["device_id"], "team_id": fd["team_id"],
        "agency_id": fd.get("agency_id", 0), "incident_id": incident,
        "schema_version": 1, "base_seq": base_seq, "base_t": base_t,
        "event_count": len(evts),
    }
    packed = [{
        "type": EventType.CELL_STATUS_REPORTED,
        "seq_delta": e["seq"] - base_seq,
        "t_delta": int(datetime.fromisoformat(e["t_dev"]).timestamp())
                   - int(INCIDENT_START.timestamp()) - base_t,
        "responder_id": e["responder_id"], "payload": e["payload"],
    } for e in evts]
    return binascii.hexlify(compute_mac(secret, encode_payload(header, packed))).decode()


def _post(anon_api, token, body):
    return anon_api.post("/v1/events", json=body, headers={"Authorization": f"Bearer {token}"})


def _event_count(owner_engine):
    with owner_engine.begin() as conn:
        return conn.execute(text(
            "SELECT COUNT(*) FROM event WHERE type = :t"
        ), {"t": EVENT_TYPE_CODE[EventType.CELL_STATUS_REPORTED]}).scalar_one()


# ─────────────────────────── the five TR-10 cases ──────────────────────

def test_tr10_valid_mac_is_accepted(gateway, anon_api, incident, owner_engine):
    gw, fd, secret = gateway
    evts = _events(fd, incident)
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-1", "origin_device_id": fd["device_id"],
        "mac": _mac_for(evts, fd, incident, secret), "events": evts})
    assert r.status_code == 200, r.text
    assert len(r.json()["accepted"]) == 1
    assert _event_count(owner_engine) == 1


def test_tr10_tampered_payload_is_rejected_and_nothing_persists(gateway, anon_api, incident, owner_engine):
    gw, fd, secret = gateway
    evts = _events(fd, incident)
    mac = _mac_for(evts, fd, incident, secret)
    evts[0]["payload"]["cell_index"] = 215          # tamper AFTER computing the MAC
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-2", "origin_device_id": fd["device_id"], "mac": mac, "events": evts})
    assert r.status_code == 401, r.text
    assert _event_count(owner_engine) == 0, "zero events must persist"


def test_tr10_tampered_header_field_is_rejected(gateway, anon_api, incident, owner_engine):
    """DM-23: the header is inside the MAC, so altering attribution must fail."""
    gw, fd, secret = gateway
    evts = _events(fd, incident)
    mac = _mac_for(evts, fd, incident, secret)
    evts[0]["responder_id"] = evts[0]["responder_id"] + 1
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-3", "origin_device_id": fd["device_id"], "mac": mac, "events": evts})
    assert r.status_code == 401
    assert _event_count(owner_engine) == 0


def test_tr10_wrong_secret_is_rejected(gateway, anon_api, incident, owner_engine):
    gw, fd, _ = gateway
    evts = _events(fd, incident)
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-4", "origin_device_id": fd["device_id"],
        "mac": _mac_for(evts, fd, incident, b"\x00" * 32), "events": evts})
    assert r.status_code == 401
    assert _event_count(owner_engine) == 0


def test_tr10_missing_mac_on_a_gateway_batch_is_rejected(gateway, anon_api, incident, owner_engine):
    gw, fd, _ = gateway
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-5", "origin_device_id": fd["device_id"],
        "events": _events(fd, incident)})
    assert r.status_code == 401
    assert _event_count(owner_engine) == 0


# ───────────────────────── boundary of the rule ────────────────────────

def test_field_batches_need_no_mac(field_device, anon_api, incident, owner_engine):
    """FIELD arrives over TLS with its device_id bound; only GATEWAY needs a MAC."""
    token, device_id, team_id = field_device
    r = anon_api.post("/v1/events", json={
        "batch_id": "b-6", "events": [{
            "device_id": device_id, "seq": 5001, "type": "CELL_STATUS_REPORTED",
            "entity_type": "CELL", "entity_id": 214,
            "payload": {"cell_index": 214, "status": "SEARCHED"},
            "t_dev": "2026-08-22T10:00:00+00:00", "responder_id": device_id,
            "team_id": team_id, "agency_id": 0, "incident_id": incident,
            "schema_version": 1}]},
        headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_tr10_failure_is_request_level_never_per_event(gateway, anon_api, incident, owner_engine):
    """AP-22: a MAC failure fails the whole request; no event may be REJECTED."""
    gw, fd, secret = gateway
    evts = _events(fd, incident, n=3)
    mac = _mac_for(evts, fd, incident, secret)
    evts[1]["payload"]["cell_index"] = 7
    r = _post(anon_api, gw["token"], {
        "batch_id": "b-7", "origin_device_id": fd["device_id"], "mac": mac, "events": evts})
    assert r.status_code == 401
    assert "rejected" not in r.json() or not r.json().get("rejected")
    assert _event_count(owner_engine) == 0
