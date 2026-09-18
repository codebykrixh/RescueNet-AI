"""M5 — authentication, authorization, enrolment, sessions, join codes.

Covers TR-22 (integration half) and TR-33. **TR-10 is deliberately absent** —
batch MAC verification is M8 (DM-49) and must not be falsely marked passing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text, update

from rescuenet.services import credentials
from rescuenet.store.tables import device_credential, join_code
from tests.integration.conftest import BOOTSTRAP_PASSWORD

pytestmark = pytest.mark.integration


# ═══════════════════ authentication ═══════════════════
UNAUTH_ENDPOINTS = [
    ("get", "/v1/diag/sync"), ("get", "/v1/events"),
    ("get", "/v1/incidents/9/snapshot"), ("get", "/v1/incidents/9/export"),
]


@pytest.mark.parametrize("method,path", UNAUTH_ENDPOINTS)
def test_endpoints_reject_missing_credentials(anon_api, bootstrap_incident, method, path):
    r = getattr(anon_api, method)(path)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_health_remains_unauthenticated(anon_api):
    """docs/09 §1.1 — endpoint 14 is the only one with Auth: None."""
    assert anon_api.get("/health").status_code == 200


def test_write_endpoints_reject_missing_credentials(anon_api, bootstrap_incident):
    assert anon_api.post("/v1/incidents", json={
        "name": "X", "disaster_type": "OTHER", "origin_lat": 0.0,
        "origin_lon": 0.0, "started_at": "2026-08-22T08:40:00Z"}).status_code == 401
    assert anon_api.post("/v1/events", json={"events": [{}]}).status_code == 401


def test_garbage_token_is_rejected(anon_api, bootstrap_incident):
    anon_api.headers.update({"Authorization": "Bearer not-a-real-token"})
    assert anon_api.get("/v1/diag/sync").status_code == 401


def test_malformed_authorization_header_is_rejected(anon_api, bootstrap_incident):
    for header in ("", "Bearer", "Basic abc", "Bearer   "):
        anon_api.headers.update({"Authorization": header})
        assert anon_api.get("/v1/diag/sync").status_code == 401


# ═══════════════════ session (endpoint 2) ═══════════════════
def test_session_login_succeeds(anon_api, bootstrap_incident):
    r = anon_api.post("/v1/auth/session", json={
        "incident_id": bootstrap_incident, "password": BOOTSTRAP_PASSWORD})
    assert r.status_code == 200
    b = r.json()
    assert b["role"] == "COMMANDER" and b["incident_id"] == bootstrap_incident
    assert len(b["token"]) == 43


def test_session_login_wrong_password_is_401(anon_api, bootstrap_incident):
    r = anon_api.post("/v1/auth/session", json={
        "incident_id": bootstrap_incident, "password": "wrong"})
    assert r.status_code == 401


def test_session_login_unknown_incident_is_404(anon_api, bootstrap_incident):
    assert anon_api.post("/v1/auth/session", json={
        "incident_id": 4242, "password": BOOTSTRAP_PASSWORD}).status_code == 404


def test_session_expiry_is_24h_from_issue(anon_api, bootstrap_incident):
    b = anon_api.post("/v1/auth/session", json={
        "incident_id": bootstrap_incident, "password": BOOTSTRAP_PASSWORD}).json()
    delta = datetime.fromisoformat(b["expires_at"]) - datetime.now(timezone.utc)
    assert timedelta(hours=23, minutes=55) < delta <= timedelta(hours=24)


def test_expired_session_is_refused(anon_api, api, commander, app_engine,
                                    bootstrap_incident):
    """DM-46 — expiry is derived from issued_at, so ageing the row expires it."""
    with app_engine.begin() as conn:
        conn.execute(update(device_credential)
                     .where(device_credential.c.token_hash
                            == credentials.hash_token(commander))
                     .values(issued_at=datetime.now(timezone.utc) - timedelta(hours=25)))
    assert api.get("/v1/diag/sync").status_code == 401


def test_session_consumes_no_device_id(app_engine, commander):
    """DM-50 — a session must not consume the 1..4095 handset space."""
    with app_engine.begin() as conn:
        row = conn.execute(select(device_credential).where(
            device_credential.c.token_hash == credentials.hash_token(commander))
        ).mappings().one()
    assert row["device_id"] is None
    assert row["role"] == "COMMANDER"
    assert row["incident_id"] is not None


# ═══════════════════ revocation ═══════════════════
def test_revoked_token_stops_working(api, commander, app_engine):
    assert api.get("/v1/diag/sync").status_code == 200
    with app_engine.begin() as conn:
        conn.execute(update(device_credential)
                     .where(device_credential.c.token_hash
                            == credentials.hash_token(commander))
                     .values(revoked_at=datetime.now(timezone.utc)))
    r = api.get("/v1/diag/sync")
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_REVOKED"


def test_revoked_device_cannot_upload(device_api, gridded, app_engine):
    with app_engine.begin() as conn:
        conn.execute(update(device_credential)
                     .where(device_credential.c.device_id == device_api.device_id)
                     .values(revoked_at=datetime.now(timezone.utc)))
    assert device_api.post("/v1/events", json={"events": []}).status_code == 401


# ═══════════════════ token storage ═══════════════════
def test_plaintext_token_is_never_stored(app_engine, commander):
    with app_engine.begin() as conn:
        stored = conn.execute(select(device_credential.c.token_hash)).scalars().all()
    assert commander not in stored
    assert credentials.hash_token(commander) in stored
    assert all(len(h) == 64 for h in stored)


def test_password_plaintext_is_never_stored(app_engine, bootstrap_incident):
    with app_engine.begin() as conn:
        h = conn.execute(text("select password_hash from incident where incident_id=:i"),
                         {"i": bootstrap_incident}).scalar_one()
    assert BOOTSTRAP_PASSWORD not in h
    assert h.startswith("scrypt$n=16384,r=8,p=1$")


# ═══════════════════ roles ═══════════════════
def test_field_device_cannot_use_commander_endpoints(device_api, gridded):
    for method, path, body in [
        ("post", "/v1/assignments", {"team_id": 3, "cell_ids": [1], "incident_id": gridded}),
        ("get", "/v1/diag/sync", None),
        ("get", f"/v1/incidents/{gridded}/export", None),
    ]:
        r = (device_api.post(path, json=body) if method == "post"
             else device_api.get(path))
        assert r.status_code == 403, f"{method} {path}"
        assert r.json()["error"]["code"] == "FORBIDDEN"


def test_commander_cannot_upload_events(api, gridded):
    """`POST /v1/events` is Device or Gateway — a session is refused."""
    r = api.post("/v1/events", json={"events": []})
    assert r.status_code == 403


def test_field_device_may_read_events_and_snapshot(device_api, gridded):
    assert device_api.get("/v1/events").status_code == 200
    assert device_api.get(f"/v1/incidents/{gridded}/snapshot?scope=field").status_code == 200


def test_scope_command_requires_commander(device_api, gridded):
    """docs/09 §1.2 endpoint 9 — scope is constrained by role."""
    r = device_api.get(f"/v1/incidents/{gridded}/snapshot?scope=command")
    assert r.status_code == 403


def test_commander_may_use_scope_command(api, gridded):
    assert api.get(f"/v1/incidents/{gridded}/snapshot?scope=command").status_code == 200


# ═══════════════════ incident membership ═══════════════════
def test_wrong_incident_is_refused(api, gridded):
    assert api.get("/v1/incidents/4242/snapshot").status_code == 403


def test_event_for_another_incident_is_rejected(device_api, gridded):
    """docs/09 §2.6 — WRONG_INCIDENT."""
    from tests.integration.test_api_read import _event

    ev = _event(4242, device_api.device_id, device_api.team_id, seq=1)
    b = device_api.post("/v1/events", json={"events": [ev]}).json()
    assert b["accepted"] == []
    assert b["rejected"][0]["code"] == "WRONG_INCIDENT"


# ═══════════════════ FIELD device binding (docs/09 Part 7.2) ═══════════════
def test_field_device_cannot_submit_another_devices_events(device_api, gridded):
    from tests.integration.test_api_read import _event

    ev = _event(gridded, device_api.device_id + 500, device_api.team_id, seq=1)
    b = device_api.post("/v1/events", json={"events": [ev]}).json()
    assert b["accepted"] == []
    assert b["rejected"][0]["code"] == "ATTRIBUTION_MISMATCH"


def test_gateway_relay_without_a_mac_is_now_refused(gateway_device, anon_api, gridded,
                                                    field_device):
    """**DM-51 is closed by M8.** Updated 2026-08-24.

    This test previously asserted that a gateway could relay another device's
    events with nothing proving authorship — the transitional state DM-51
    described as lasting *"until M8"*. M8 has now supplied the codec and TR-10,
    so a `GATEWAY` batch without a valid MAC is refused outright: **401, zero
    events persisted** (`11` TR-10, AP-16).

    The positive path — a gateway relaying a *different* device's events with a
    valid MAC, which is still permitted — is covered by
    ``test_tr10_valid_mac_is_accepted`` in ``test_tr10_batch_mac.py``.
    """
    from fastapi.testclient import TestClient

    from tests.integration.test_api_read import _event

    token, _ = gateway_device
    _, other_device_id, other_team = field_device
    gw = TestClient(anon_api.app)
    gw.headers.update({"Authorization": f"Bearer {token}"})
    ev = _event(gridded, other_device_id, other_team, seq=77)
    r = gw.post("/v1/events", json={"events": [ev]})
    assert r.status_code == 401, "a MAC-less GATEWAY batch must be refused (TR-10)"


# ═══════════════════ TR-22 · SEQ_NOT_MONOTONIC ═══════════════════
def test_tr22_seq_going_backwards_is_rejected(device_api, gridded):
    from tests.integration.test_api_read import _event

    d, tm = device_api.device_id, device_api.team_id
    device_api.post("/v1/events", json={"events": [_event(gridded, d, tm, seq=10)]})
    b = device_api.post("/v1/events",
                        json={"events": [_event(gridded, d, tm, seq=5)]}).json()
    assert b["accepted"] == []
    assert b["rejected"][0]["code"] == "SEQ_NOT_MONOTONIC"


def test_tr22_gaps_are_accepted(device_api, gridded):
    """DM-13 — gaps are legal; only going backwards is not."""
    from tests.integration.test_api_read import _event

    d, tm = device_api.device_id, device_api.team_id
    device_api.post("/v1/events", json={"events": [_event(gridded, d, tm, seq=1)]})
    b = device_api.post("/v1/events",
                        json={"events": [_event(gridded, d, tm, seq=500)]}).json()
    assert len(b["accepted"]) == 1


def test_tr22_replay_of_same_seq_is_still_idempotent(device_api, gridded):
    """M3 dedup semantics unchanged: a replay is accepted as a duplicate."""
    from tests.integration.test_api_read import _event

    d, tm = device_api.device_id, device_api.team_id
    device_api.post("/v1/events", json={"events": [_event(gridded, d, tm, seq=7)]})
    b = device_api.post("/v1/events",
                        json={"events": [_event(gridded, d, tm, seq=7)]}).json()
    assert b["accepted"][0]["was_duplicate"] is True


def test_tr22_device_ids_start_at_one(app_engine, field_device):
    _, device_id, _ = field_device
    assert 1 <= device_id <= 4095, "0 is reserved for the server (DM-36)"


# ═══════════════════ TR-33 · enrolment ═══════════════════
def test_tr33_enrolment_is_not_idempotent(api, incident, anon_api):
    """AP-02 — two enrolments with one code yield two distinct device_ids."""
    code = api.post("/v1/teams/3/join-code",
                    json={"incident_id": incident, "max_uses": 5}).json()["join_code"]
    a = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"}).json()
    b = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"}).json()
    assert a["device_id"] != b["device_id"]
    assert a["token"] != b["token"]


def test_tr33_exhausted_code_is_409(api, incident, anon_api):
    code = api.post("/v1/teams/3/join-code",
                    json={"incident_id": incident, "max_uses": 1}).json()["join_code"]
    assert anon_api.post("/v1/enrol", json={"join_code": code,
                                            "mode": "FIELD"}).status_code == 201
    r = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "JOIN_CODE_EXHAUSTED"


def test_tr33_expired_code_is_409(api, incident, anon_api, app_engine):
    code = api.post("/v1/teams/3/join-code",
                    json={"incident_id": incident}).json()["join_code"]
    with app_engine.begin() as conn:
        conn.execute(update(join_code).where(join_code.c.code == code)
                     .values(expires_at=datetime.now(timezone.utc) - timedelta(hours=1)))
    r = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "JOIN_CODE_EXPIRED"


def test_unknown_join_code_is_404(anon_api, bootstrap_incident):
    assert anon_api.post("/v1/enrol", json={"join_code": "ZZZZZZ",
                                            "mode": "FIELD"}).status_code == 404


def test_enrolment_returns_secret_once_and_persists_it_recoverably(api, incident,
                                                                   anon_api, app_engine):
    """DM-47 — the secret is recoverable so M8 can recompute MACs."""
    import base64

    code = api.post("/v1/teams/3/join-code",
                    json={"incident_id": incident}).json()["join_code"]
    b = anon_api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"}).json()
    assert "hmac_secret" in b
    with app_engine.begin() as conn:
        stored = conn.execute(select(device_credential.c.hmac_secret).where(
            device_credential.c.device_id == b["device_id"])).scalar_one()
    assert stored == base64.b64decode(b["hmac_secret"]), "recoverable, not hashed"
    assert len(stored) == 32


def test_join_code_shape(api, incident):
    b = api.post("/v1/teams/3/join-code", json={"incident_id": incident}).json()
    code = b["join_code"]
    assert len(code) == 6
    assert set(code) <= set(credentials.JOIN_CODE_ALPHABET)
    assert not (set(code) & set("ILO01")), "confusable characters excluded"


def test_join_code_requires_a_session(anon_api, bootstrap_incident):
    assert anon_api.post("/v1/teams/3/join-code",
                         json={"incident_id": bootstrap_incident}).status_code == 401


# ═══════════════════ TR-10 is NOT implemented here ═══════════════════
def test_tr10_batch_mac_verification_is_deferred_to_m8():
    """TR-10 is owned by M8 (DM-49) and must not be falsely marked passing.

    This asserts the *absence* of a MAC verifier, so the suite cannot silently
    start claiming a guarantee that does not exist yet.
    """
    import rescuenet.services.ingestion as ingestion

    source = __import__("inspect").getsource(ingestion)
    assert "hmac" not in source.lower(), "no MAC verification may exist before M8"
    assert "verify_mac" not in source
