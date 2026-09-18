"""The canonical event: schema fidelity, all 11 types, validation (docs/08)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from rescuenet.domain import (
    PAYLOAD_MODEL, CanonicalEvent, EntityType, EventType, Priority,
    entity_type_for, priority_for,
)

pytestmark = pytest.mark.unit

CANONICAL_FIELDS = {
    "device_id", "seq", "type", "entity_type", "entity_id", "payload",
    "t_dev", "t_srv", "server_seq", "schema_version",
    "responder_id", "team_id", "agency_id", "incident_id", "received_via",
}


# ------------------------------------------------- schema fidelity
def test_schema_is_exactly_docs08_part_1_1():
    assert set(CanonicalEvent.model_fields) == CANONICAL_FIELDS


@pytest.mark.parametrize(
    "forbidden",
    ["priority", "mac", "retryable", "rejected_code", "outbox_state",
     "duplicate_search", "topic", "qos", "retain", "transport", "batch_id"],
)
def test_forbidden_fields_are_absent_from_the_schema(forbidden):
    """No priority (DM-02), no MAC (DM-03), no transport/MQTT/outbox fields."""
    assert forbidden not in CanonicalEvent.model_fields


def test_undeclared_field_is_rejected_not_silently_kept(raw_event):
    with pytest.raises(ValidationError):
        CanonicalEvent(**(raw_event() | {"priority": "CRITICAL"}))


def test_events_are_immutable(canonical_event):
    with pytest.raises(ValidationError):
        canonical_event().payload = {}


# ------------------------------------------------- the 11 types
def test_exactly_eleven_event_types():
    assert len(list(EventType)) == 11


def test_no_forbidden_event_type_exists():
    """DM-07/DM-08/DM-09/DM-39 — these must never become event types."""
    names = {t.value for t in EventType}
    for absent in ("DUPLICATE_SEARCH", "DUPLICATE_SEARCH_FLAGGED", "ACK",
                   "SYNC_ACK", "REJECTED", "AUDIT", "HEARTBEAT"):
        assert absent not in names


def test_every_type_has_a_payload_model():
    assert set(PAYLOAD_MODEL) == set(EventType)


@pytest.mark.parametrize("event_type", list(EventType))
def test_entity_type_is_implied_by_event_type(event_type):
    assert isinstance(entity_type_for(event_type), EntityType)


def test_mismatched_entity_type_is_rejected(raw_event):
    with pytest.raises(ValidationError, match="implies entity_type"):
        CanonicalEvent(**(raw_event() | {"entity_type": "TEAM"}))


def test_entity_id_disagreeing_with_payload_is_rejected(raw_event):
    with pytest.raises(ValidationError, match="disagrees"):
        CanonicalEvent(**(raw_event() | {"entity_id": 999}))


def test_survivor_report_entity_id_is_zero(load_shared_fixture):
    e = CanonicalEvent(**load_shared_fixture("survivor_reported.json"))
    assert e.entity_id == 0  # the event IS the entity (docs/08 §16.4)


# ------------------------------------------------- derived priority
def test_only_survivor_reported_is_critical():
    critical = [t for t in EventType if priority_for(t) is Priority.CRITICAL]
    assert critical == [EventType.SURVIVOR_REPORTED]


def test_priority_changes_with_type_and_nothing_else(raw_event):
    """DM-02 — one source of truth: change the type, the priority follows."""
    routine = CanonicalEvent(**raw_event())
    assert routine.priority is Priority.ROUTINE

    survivor = CanonicalEvent(
        **raw_event(
            type="SURVIVOR_REPORTED", entity_type="SURVIVOR", entity_id=0,
            payload={"cell_index": 214, "person_count": 1,
                     "survivor_status": "TRAPPED"},
        )
    )
    assert survivor.priority is Priority.CRITICAL


def test_priority_is_deterministic():
    for event_type in EventType:
        assert priority_for(event_type) is priority_for(event_type)


def test_priority_cannot_be_set_on_an_event(raw_event):
    with pytest.raises(ValidationError):
        CanonicalEvent(**(raw_event() | {"priority": "ROUTINE"}))


# ------------------------------------------------- payload validation
def test_payload_missing_a_required_field_is_rejected(raw_event):
    with pytest.raises(ValidationError, match="payload invalid"):
        CanonicalEvent(**raw_event(payload={"cell_index": 214}))


def test_payload_with_an_extra_field_is_rejected(raw_event):
    with pytest.raises(ValidationError, match="payload invalid"):
        CanonicalEvent(
            **raw_event(payload={"cell_index": 214, "status": "SEARCHED", "x": 1})
        )


def test_payload_enum_value_must_be_known(raw_event):
    with pytest.raises(ValidationError, match="payload invalid"):
        CanonicalEvent(**raw_event(payload={"cell_index": 214, "status": "MAYBE"}))


def test_cell_index_above_max_is_rejected(raw_event):
    with pytest.raises(ValidationError):
        CanonicalEvent(
            **raw_event(entity_id=8191, payload={"cell_index": 8191,
                                                 "status": "SEARCHED"})
        )


def test_cell_index_at_max_valid_is_accepted(raw_event):
    e = CanonicalEvent(
        **raw_event(entity_id=8190, payload={"cell_index": 8190,
                                             "status": "SEARCHED"})
    )
    assert e.typed_payload().cell_index == 8190


def test_grid_payload_rejects_a_grid_over_max_cells(raw_event):
    with pytest.raises(ValidationError):
        CanonicalEvent(
            **raw_event(
                type="GRID_GENERATED", entity_type="GRID", entity_id=9,
                payload={"origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 10.0,
                         "rows": 100, "cols": 100, "bearing_deg": 0.0},
            )
        )


def test_typed_payload_returns_the_model(canonical_event):
    from rescuenet.domain.payloads import CellStatusReportedPayload

    assert isinstance(canonical_event().typed_payload(), CellStatusReportedPayload)
