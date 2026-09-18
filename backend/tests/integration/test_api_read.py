"""M4 endpoints 7, 8, 9, 12, 13 under M5 authentication.

TR-05, TR-06, TR-07, TR-21, TR-27, TR-34. Uploads use a FIELD device because
`POST /v1/events` is `Device or Gateway`; reads use the COMMANDER session.
"""
from __future__ import annotations

import csv
import io
import json

import pytest

pytestmark = pytest.mark.integration


def _event(incident_id, device_id, team_id, *, seq=1, type="CELL_STATUS_REPORTED",
           entity_type="CELL", entity_id=214, payload=None):
    return {
        "device_id": device_id, "seq": seq, "type": type,
        "entity_type": entity_type, "entity_id": entity_id,
        "payload": payload if payload is not None
        else {"cell_index": 214, "status": "SEARCHED"},
        "t_dev": "2026-08-22T10:00:14Z", "responder_id": device_id,
        "team_id": team_id, "agency_id": 1, "incident_id": incident_id,
        "schema_version": 1,
    }


def _post(dev, incident_id, **kw):
    return dev.post("/v1/events", json={"events": [
        _event(incident_id, dev.device_id, dev.team_id, **kw)]})


# ═══════════ 7 · POST /v1/events — TR-07 partial acceptance ═══════════
def test_batch_accepts_valid_events(device_api, gridded):
    d, tm = device_api.device_id, device_api.team_id
    r = device_api.post("/v1/events", json={"events": [
        _event(gridded, d, tm, seq=1), _event(gridded, d, tm, seq=2)]})
    assert r.status_code == 200
    b = r.json()
    assert len(b["accepted"]) == 2 and b["rejected"] == []
    assert set(b) == {"accepted", "rejected", "server_seq_high"}


def test_partial_acceptance_returns_200(device_api, gridded):
    """AP-04 — one bad event must not block the good ones."""
    d, tm = device_api.device_id, device_api.team_id
    r = device_api.post("/v1/events", json={"events": [
        _event(gridded, d, tm, seq=1),
        _event(gridded, d, tm, seq=2, type="TELEPORTED"),
        _event(gridded, d, tm, seq=3)]})
    assert r.status_code == 200
    b = r.json()
    assert len(b["accepted"]) == 2 and len(b["rejected"]) == 1
    assert b["rejected"][0]["code"] == "UNKNOWN_TYPE"
    assert b["rejected"][0]["retryable"] is False


def test_duplicate_is_accepted_and_flagged(device_api, gridded):
    _post(device_api, gridded, seq=1)
    r = _post(device_api, gridded, seq=1)
    assert r.json()["accepted"][0]["was_duplicate"] is True


def test_malformed_payload_rejected_individually(device_api, gridded):
    d, tm = device_api.device_id, device_api.team_id
    r = device_api.post("/v1/events", json={"events": [
        _event(gridded, d, tm, seq=1, payload={"nope": 1}),
        _event(gridded, d, tm, seq=2)]})
    b = r.json()
    assert len(b["accepted"]) == 1 and b["rejected"][0]["code"] == "INVALID_PAYLOAD"


def test_tr05_unknown_cell_on_routine_is_rejected(device_api, gridded):
    r = _post(device_api, gridded, seq=1, entity_id=8191,
              payload={"cell_index": 8191, "status": "SEARCHED"})
    b = r.json()
    assert b["accepted"] == []
    assert b["rejected"][0]["code"] in ("UNKNOWN_CELL", "INVALID_PAYLOAD")


def test_tr06_critical_survivor_is_never_lost(device_api, gridded):
    """AP-20 — a mistyped cell_index must not discard a survivor's location."""
    r = _post(device_api, gridded, seq=1, type="SURVIVOR_REPORTED",
              entity_type="SURVIVOR", entity_id=0,
              payload={"cell_index": 214, "person_count": 2,
                       "survivor_status": "TRAPPED"})
    assert len(r.json()["accepted"]) == 1


# ═══════════ 8 · GET /v1/events — TR-21 ═══════════
def test_delta_cursor_is_server_seq(device_api, gridded):
    for i in range(1, 6):
        _post(device_api, gridded, seq=i)
    first = device_api.get("/v1/events?since=0&limit=2").json()
    assert len(first["events"]) == 2 and first["has_more"] is True
    seqs = [e["server_seq"] for e in first["events"]]
    assert seqs == sorted(seqs)
    second = device_api.get(f"/v1/events?since={first['next_since']}&limit=2").json()
    assert all(e["server_seq"] > first["next_since"] for e in second["events"])


def test_same_cursor_same_page(device_api, gridded):
    for i in range(1, 4):
        _post(device_api, gridded, seq=i)
    assert device_api.get("/v1/events?since=0&limit=2").json() == \
           device_api.get("/v1/events?since=0&limit=2").json()


def test_paging_reaches_the_end(device_api, gridded):
    for i in range(1, 4):
        _post(device_api, gridded, seq=i)
    since, guard, page = 0, 0, None
    while guard < 20:
        page = device_api.get(f"/v1/events?since={since}&limit=2").json()
        since = page["next_since"]
        guard += 1
        if not page["has_more"]:
            break
    assert page["has_more"] is False


def test_limit_boundaries(device_api, gridded):
    assert device_api.get("/v1/events?limit=1").status_code == 200
    assert device_api.get("/v1/events?limit=1000").status_code == 200
    assert device_api.get("/v1/events?limit=0").status_code == 422
    assert device_api.get("/v1/events?limit=1001").status_code == 422


def test_audit_filter_by_entity(device_api, second_device_api, gridded):
    """TR-32 at the API boundary — two teams on one cell."""
    _post(device_api, gridded, seq=1)
    _post(second_device_api, gridded, seq=1)
    r = device_api.get("/v1/events?entity_type=CELL&entity_id=214").json()
    assert len(r["events"]) == 2
    assert {e["team_id"] for e in r["events"]} == {3, 5}


# ═══════════ 9 · snapshot — TR-27 ═══════════
def test_snapshot_cell_state_is_positional(api, device_api, gridded):
    _post(device_api, gridded, seq=1)
    b = api.get(f"/v1/incidents/{gridded}/snapshot").json()
    assert b["cell_state"] == [[214, "SEARCHED", 3]]


def test_snapshot_omits_untouched_cells(api, device_api, gridded):
    """DM-12 — one searched cell in a 5,000-cell grid yields one entry."""
    _post(device_api, gridded, seq=1)
    b = api.get(f"/v1/incidents/{gridded}/snapshot").json()
    assert len(b["cell_state"]) == 1
    assert b["grid"]["rows"] * b["grid"]["cols"] == 5000


def test_snapshot_carries_grid_and_cursor(api, gridded):
    b = api.get(f"/v1/incidents/{gridded}/snapshot").json()
    assert b["grid"]["cols"] == 200 and b["grid"]["rows"] == 25
    assert isinstance(b["current_server_seq"], int)


def test_snapshot_contains_no_cell_labels(api, device_api, gridded):
    _post(device_api, gridded, seq=1)
    assert "label" not in json.dumps(api.get(f"/v1/incidents/{gridded}/snapshot").json())


def test_snapshot_unknown_incident_is_403_not_404(api):
    """Authorization precedes existence disclosure — 4242 is not revealed."""
    assert api.get("/v1/incidents/4242/snapshot").status_code == 403


def test_snapshot_duplicate_search_surfaces_both_teams(api, device_api,
                                                       second_device_api, gridded):
    """D-01b end to end through the authenticated API."""
    _post(device_api, gridded, seq=1)
    _post(second_device_api, gridded, seq=1)
    d = api.get(f"/v1/incidents/{gridded}/snapshot").json()["duplicate_search"]
    assert len(d) == 1 and sorted(d[0]["team_ids"]) == [3, 5]


# ═══════════ 12 · export — TR-34 ═══════════
def test_geojson_export_is_valid(api, device_api, gridded):
    _post(device_api, gridded, seq=1)
    r = api.get(f"/v1/incidents/{gridded}/export?format=geojson")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/geo+json")
    fc = r.json()
    cell = [f for f in fc["features"] if f["properties"].get("cell_index") == 214][0]
    assert cell["geometry"]["type"] == "Polygon"
    assert len(cell["geometry"]["coordinates"][0]) == 5
    assert cell["properties"]["label"] == "O-2"


def test_csv_export_has_documented_columns(api, device_api, gridded):
    _post(device_api, gridded, seq=1)
    r = api.get(f"/v1/incidents/{gridded}/export?format=csv")
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["cell_index", "label", "status", "team_id"]
    assert rows[1][:3] == ["214", "O-2", "SEARCHED"]


def test_export_rejects_unknown_format(api, gridded):
    assert api.get(f"/v1/incidents/{gridded}/export?format=xml").status_code == 422


# ═══════════ 13 · diagnostics ═══════════
def test_diagnostics_shape(api, device_api, gridded):
    _post(device_api, gridded, seq=1)
    b = api.get("/v1/diag/sync").json()
    assert set(b) == {"current_server_seq", "events_total", "events_by_transport",
                      "projection_lag", "mqtt_connected", "last_publish_server_seq"}
    assert b["events_total"] >= 1
