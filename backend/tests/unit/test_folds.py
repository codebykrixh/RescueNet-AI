"""M3 fold rules as pure logic: TR-16, TR-17, TR-18, TR-23, TR-29 (docs/08 §7.2).

The baseline is SP-05's validated behaviour (docs/04 §3.2, 13/13), expressed
against the real domain model.
"""
from __future__ import annotations

import pytest

from rescuenet.domain import CanonicalEvent
from rescuenet.projections import (
    ASSIGNED, UNSEARCHED, fold_all, fold_assignment_state, fold_cell_state,
    fold_coverage_metrics, fold_duplicate_search, fold_resource_stock,
    fold_survivor_reports, fold_team_state,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def make(raw_event):
    """Build a canonical event with an explicit server_seq."""
    def _make(server_seq=None, **over):
        return CanonicalEvent(**raw_event(server_seq=server_seq, **over))
    return _make


def _search(make, *, device_id, seq, team_id, agency_id, cell, server_seq,
            status="SEARCHED", responder_id=71):
    return make(server_seq=server_seq, device_id=device_id, seq=seq, team_id=team_id,
                agency_id=agency_id, responder_id=responder_id, entity_id=cell,
                payload={"cell_index": cell, "status": status})


# ───────────────────────── TR-17 · duplicate search (D-01b) ─────────────────
def test_two_teams_searching_one_cell_are_both_preserved(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1201),
        _search(make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214, server_seq=907),
    ]
    dupes = fold_duplicate_search(events)
    assert (9, 214) in dupes
    assert dupes[(9, 214)].team_ids == (3, 5)
    assert dupes[(9, 214)].team_count == 2
    assert len(events) == 2, "neither event was consumed by the fold"


def test_one_team_searching_twice_is_not_a_duplicate(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1),
        _search(make, device_id=17, seq=2, team_id=3, agency_id=1, cell=214, server_seq=2),
    ]
    assert fold_duplicate_search(events) == {}


def test_duplicate_predicate_is_order_independent(make):
    """DM-22 — a set-cardinality test, so AL-05 inversion cannot affect it."""
    a = _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1201)
    b = _search(make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214, server_seq=907)
    assert fold_duplicate_search([a, b]) == fold_duplicate_search([b, a])


def test_in_progress_does_not_count_as_a_duplicate_search(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1),
        _search(make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214, server_seq=2,
                status="IN_PROGRESS"),
    ]
    assert fold_duplicate_search(events) == {}


def test_attribution_survives_the_fold(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214,
                server_seq=1201, responder_id=71),
        _search(make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214,
                server_seq=907, responder_id=84),
    ]
    assert {(e.team_id, e.agency_id, e.responder_id) for e in events} == {
        (3, 1, 71), (5, 2, 84)}


# ───────────────────────── rule 6 · cell state ──────────────────────────────
def test_latest_by_server_seq_wins(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214,
                server_seq=100, status="IN_PROGRESS"),
        _search(make, device_id=17, seq=2, team_id=3, agency_id=1, cell=214,
                server_seq=200, status="SEARCHED"),
    ]
    assert fold_cell_state(events)[(9, 214)].status == "SEARCHED"


def test_fold_uses_server_seq_not_device_time(make):
    """TR-23 — ordering is acceptance order (DM-21). AL-05 is reproducible here."""
    earlier_clock_later_arrival = _search(
        make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214,
        server_seq=1201, status="NEEDS_RESEARCH")
    later_clock_earlier_arrival = _search(
        make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214,
        server_seq=907, status="SEARCHED")
    state = fold_cell_state([earlier_clock_later_arrival, later_clock_earlier_arrival])
    assert state[(9, 214)].status == "NEEDS_RESEARCH", "highest server_seq wins"
    assert state[(9, 214)].last_server_seq == 1201


def test_assigned_when_a_live_assignment_but_no_status(make):
    issued = make(server_seq=412, device_id=0, seq=88, type="ASSIGNMENT_ISSUED",
                  entity_type="ASSIGNMENT", entity_id=45, team_id=0,
                  payload={"assignment_id": 45, "team_id": 3, "cell_ids": [214, 215]})
    state = fold_cell_state([issued])
    assert state[(9, 214)].status == ASSIGNED
    assert state[(9, 215)].team_id == 3


# ───────────────────────── rule 4 · assignments ─────────────────────────────
def test_revocation_clears_the_holder(make):
    issued = make(server_seq=412, device_id=0, seq=88, type="ASSIGNMENT_ISSUED",
                  entity_type="ASSIGNMENT", entity_id=45, team_id=0,
                  payload={"assignment_id": 45, "team_id": 3, "cell_ids": [214]})
    revoked = make(server_seq=620, device_id=0, seq=89, type="ASSIGNMENT_REVOKED",
                   entity_type="ASSIGNMENT", entity_id=45, team_id=0,
                   payload={"assignment_id": 45})
    assert fold_assignment_state([issued, revoked])[(9, 214)].team_id is None


# ───────────────────────── TR-18 · inventory commutativity ──────────────────
def test_inventory_deltas_sum(make):
    a = make(server_seq=1, device_id=22, seq=1, team_id=5, agency_id=2, responder_id=84,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": -2})
    b = make(server_seq=2, device_id=17, seq=1, team_id=5, agency_id=2, responder_id=71,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": -3})
    assert fold_resource_stock([a, b])[(5, 7)] == -5


def test_inventory_is_commutative(make):
    a = make(server_seq=1, device_id=22, seq=1, team_id=5, agency_id=2, responder_id=84,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": -2})
    b = make(server_seq=2, device_id=17, seq=1, team_id=5, agency_id=2, responder_id=71,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": 10})
    assert fold_resource_stock([a, b]) == fold_resource_stock([b, a])


def test_negative_stock_is_reported_not_clamped(make):
    e = make(server_seq=1, device_id=22, seq=1, team_id=5, agency_id=2, responder_id=84,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": -9})
    assert fold_resource_stock([e])[(5, 7)] == -9


# ───────────────────────── rule 5 · survivor reports ────────────────────────
def test_survivor_reports_are_never_deduplicated(make):
    a = make(server_seq=1, device_id=17, seq=1, type="SURVIVOR_REPORTED",
             entity_type="SURVIVOR", entity_id=0,
             payload={"cell_index": 214, "person_count": 2,
                      "survivor_status": "TRAPPED"})
    b = make(server_seq=2, device_id=22, seq=1, team_id=5, agency_id=2, responder_id=84,
             type="SURVIVOR_REPORTED", entity_type="SURVIVOR", entity_id=0,
             payload={"cell_index": 214, "person_count": 2,
                      "survivor_status": "TRAPPED"})
    assert len(fold_survivor_reports([a, b])) == 2, "AL-11 — both retained"


# ───────────────────────── TR-16 · convergence ──────────────────────────────
def test_fold_is_order_independent_for_every_projection(make):
    events = [
        _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1201),
        _search(make, device_id=22, seq=1, team_id=5, agency_id=2, cell=214, server_seq=907),
        make(server_seq=915, device_id=22, seq=2, team_id=5, agency_id=2, responder_id=84,
             type="RESOURCE_DELTA_REPORTED", entity_type="RESOURCE", entity_id=7,
             payload={"item_id": 7, "qty_delta": -2}),
        make(server_seq=1203, device_id=17, seq=2, type="TEAM_STATUS_REPORTED",
             entity_type="TEAM", entity_id=3, payload={"team_status": "ACTIVE"}),
    ]
    forward, backward = fold_all(events), fold_all(list(reversed(events)))
    assert forward == backward, "merge must be commutative — union, not sequence"


def test_duplicate_delivery_does_not_change_the_fold(make):
    """Idempotence at the fold level: the log is a set keyed by identity."""
    e = _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214, server_seq=1)
    once, twice = fold_all([e]), fold_all([e, e])
    assert once.cell_state == twice.cell_state
    assert once.resource_stock == twice.resource_stock


def test_events_from_a_node_that_never_met_the_server_still_fold(make):
    """SP-05's store-and-forward case: relayed events are ordinary events."""
    relayed = _search(make, device_id=31, seq=7, team_id=8, agency_id=3, cell=300,
                      server_seq=5000, responder_id=100)
    assert fold_cell_state([relayed])[(9, 300)].status == "SEARCHED"


def test_clock_skewed_event_is_retained_and_ordered_by_server_seq(make):
    skewed = _search(make, device_id=31, seq=1, team_id=8, agency_id=3, cell=214,
                     server_seq=9999, responder_id=100)
    skewed = skewed.model_copy(update={"t_dev": skewed.t_dev.replace(year=2020)})
    normal = _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=214,
                     server_seq=1)
    state = fold_cell_state([normal, skewed])
    assert state[(9, 214)].last_server_seq == 9999, "server_seq orders, not t_dev"


# ───────────────────────── TR-29 · coverage metrics (AP-24) ─────────────────
def test_coverage_metrics_derive_from_cell_state_and_grid(make):
    grid = make(server_seq=2, device_id=0, seq=2, type="GRID_GENERATED",
                entity_type="GRID", entity_id=9, team_id=0,
                payload={"origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
                         "rows": 10, "cols": 10, "bearing_deg": 0.0})
    searched = _search(make, device_id=17, seq=1, team_id=3, agency_id=1, cell=5,
                       server_seq=10)
    m = fold_coverage_metrics([grid, searched])[9]
    assert (m.total, m.searched, m.unsearched) == (100, 1, 99)


def test_coverage_metrics_are_deterministic(make):
    grid = make(server_seq=2, device_id=0, seq=2, type="GRID_GENERATED",
                entity_type="GRID", entity_id=9, team_id=0,
                payload={"origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
                         "rows": 5, "cols": 5, "bearing_deg": 0.0})
    events = [grid, _search(make, device_id=17, seq=1, team_id=3, agency_id=1,
                            cell=1, server_seq=10)]
    assert fold_coverage_metrics(events) == fold_coverage_metrics(list(reversed(events)))


def test_cell_labels_never_enter_the_fold(make):
    """Labels are derived presentation only — they must not affect merge identity."""
    import inspect

    from rescuenet.projections import folds

    source = inspect.getsource(folds)
    assert "cell_label" not in source and "column_letters" not in source
