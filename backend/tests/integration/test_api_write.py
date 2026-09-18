"""M4 write endpoints: 3, 4, 5, 10, 11 — and the reference tables."""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from rescuenet.store.tables import incident as incident_table

pytestmark = pytest.mark.integration


# ── 3 · POST /v1/incidents ──────────────────────────────────────────────────
def test_declare_incident_creates_row_and_event(api, app_engine):
    r = api.post("/v1/incidents", json={
        "name": "Malin Landslide", "disaster_type": "LANDSLIDE",
        "origin_lat": 19.1638, "origin_lon": 73.6822,
        "started_at": "2026-08-22T08:40:00Z"})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"incident_id", "server_seq"}

    with app_engine.begin() as conn:
        row = conn.execute(
            select(incident_table).where(
                incident_table.c.incident_id == body["incident_id"])
        ).mappings().one()
        assert row["name"] == "Malin Landslide"
        n = conn.execute(text(
            "select count(*) from event where type=1 and incident_id=:i"
        ), {"i": body["incident_id"]}).scalar_one()
    assert n == 1, "exactly one INCIDENT_DECLARED for this incident"


def test_incident_event_is_server_authored(api, app_engine):
    api.post("/v1/incidents", json={
        "name": "X", "disaster_type": "OTHER", "origin_lat": 0.0,
        "origin_lon": 0.0, "started_at": "2026-08-22T08:40:00Z"})
    with app_engine.begin() as conn:
        dev = conn.execute(text("select device_id from event where type=1")).scalar_one()
    assert dev == 0, "server-authored events use the reserved device_id 0 (DM-36)"


def test_invalid_disaster_type_is_422_with_error_contract(api):
    r = api.post("/v1/incidents", json={
        "name": "X", "disaster_type": "METEOR", "origin_lat": 0.0,
        "origin_lon": 0.0, "started_at": "2026-08-22T08:40:00Z"})
    assert r.status_code == 422
    assert set(r.json()["error"]) == {"code", "message", "retryable", "details"}
    assert r.json()["error"]["retryable"] is False


# ── 4 · POST /v1/incidents/{id}/grid ────────────────────────────────────────
def test_generate_grid(api, incident):
    r = api.post(f"/v1/incidents/{incident}/grid", json={
        "origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
        "rows": 25, "cols": 200, "bearing_deg": 0.0})
    assert r.status_code == 201
    assert r.json()["cell_count"] == 5000


def test_grid_over_max_cells_is_rejected(api, incident):
    r = api.post(f"/v1/incidents/{incident}/grid", json={
        "origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 10.0,
        "rows": 100, "cols": 100})
    assert r.status_code == 422
    assert r.json()["error"]["code"] in ("INVALID_GRID", "INVALID_PAYLOAD")


def test_second_grid_is_409(api, gridded):
    r = api.post(f"/v1/incidents/{gridded}/grid", json={
        "origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
        "rows": 5, "cols": 5})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "GRID_ALREADY_GENERATED"


def test_grid_for_unknown_incident_is_403_not_404(api):
    """Authorization precedes existence disclosure (M5).

    The commander is scoped to one incident, so the membership check fires
    before the lookup — 9999 is refused without revealing whether it exists.
    """
    r = api.post("/v1/incidents/9999/grid", json={
        "origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
        "rows": 5, "cols": 5})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "WRONG_INCIDENT"


# ── 5 · POST /v1/teams ──────────────────────────────────────────────────────
def test_register_team(api, incident):
    r = api.post("/v1/teams", json={
        "team_id": 3, "callsign": "Alpha", "agency_id": 1,
        "agency_type": "NDRF", "incident_id": incident})
    assert r.status_code == 201
    assert r.json()["team_id"] == 3


# ── 10 · POST /v1/assignments ───────────────────────────────────────────────
def test_issue_assignment(api, gridded):
    r = api.post("/v1/assignments", json={
        "team_id": 3, "cell_ids": [214, 215], "incident_id": gridded})
    assert r.status_code == 201
    assert r.json()["already_held"] == []


def test_collision_returns_201_with_already_held_not_409(api, gridded):
    """AP-03 / FR-303 — the collision is surfaced, the commander is not blocked."""
    api.post("/v1/assignments", json={
        "team_id": 3, "cell_ids": [214], "incident_id": gridded})
    r = api.post("/v1/assignments", json={
        "team_id": 5, "cell_ids": [214, 215], "incident_id": gridded})
    assert r.status_code == 201, "must NOT be 409"
    held = r.json()["already_held"]
    assert held == [{"cell_index": 214, "team_id": 3}]


def test_assignment_beyond_max_cell_index_is_422(api, gridded):
    r = api.post("/v1/assignments", json={
        "team_id": 3, "cell_ids": [8191], "incident_id": gridded})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNKNOWN_CELL"


# ── 11 · DELETE /v1/assignments/{id} ────────────────────────────────────────
def test_revoke_assignment(api, gridded):
    aid = api.post("/v1/assignments", json={
        "team_id": 3, "cell_ids": [214], "incident_id": gridded}).json()["assignment_id"]
    r = api.delete(f"/v1/assignments/{aid}")
    assert r.status_code == 200 and "server_seq" in r.json()


def test_revoke_unknown_assignment_is_404(api, gridded):
    r = api.delete("/v1/assignments/424242")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "UNKNOWN_ASSIGNMENT"


# ── reference tables / FK ───────────────────────────────────────────────────
def test_reference_tables_exist(app_engine):
    with app_engine.begin() as conn:
        for table in ("incident", "agency", "resource_item"):
            assert conn.execute(text(f"select to_regclass('public.{table}')")).scalar()


def test_m5_credential_tables_exist(app_engine):
    """Created at M5 (docs/08 §11.1a/§11.1b). Never in the event log (DM-11)."""
    with app_engine.begin() as conn:
        for table in ("device_credential", "join_code"):
            assert conn.execute(text(f"select to_regclass('public.{table}')")).scalar()


def test_incident_fk_is_enforced(clean_db, app_engine):
    from rescuenet.domain import CanonicalEvent
    from rescuenet.store import append, connection
    import json

    raw = json.load(open("../shared/fixtures/cell_status_reported.json"))
    base = {k: v for k, v in raw.items()
            if k not in ("server_seq", "t_srv", "received_via")}
    with pytest.raises(Exception) as err:
        with connection(app_engine) as conn:
            append(conn, CanonicalEvent(**{**base, "incident_id": 4242}))
    assert "foreign key" in str(err.value).lower() or "violates" in str(err.value).lower()
