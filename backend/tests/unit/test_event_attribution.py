"""TR-31 — attribution completeness (FR-1002, DM-04, PS-B7)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from rescuenet.domain import CanonicalEvent
from rescuenet.domain.limits import MAX_AGENCY_ID, MAX_RESPONDER_ID, MAX_TEAM_ID

pytestmark = pytest.mark.unit

REQUIRED_ATTRIBUTION = ("responder_id", "team_id", "agency_id", "t_dev", "incident_id")


@pytest.mark.parametrize("field", REQUIRED_ATTRIBUTION)
def test_event_cannot_exist_without_attribution(raw_event, field):
    raw = raw_event()
    raw.pop(field)
    with pytest.raises(ValidationError):
        CanonicalEvent(**raw)


def test_attribution_is_carried_on_the_event_not_looked_up(canonical_event):
    """DM-04 — attribution is a point-in-time historical fact."""
    e = canonical_event(responder_id=71, team_id=3, agency_id=1)
    assert (e.responder_id, e.team_id, e.agency_id) == (71, 3, 1)


def test_attribution_survives_because_events_are_immutable(canonical_event):
    """A responder moving team must not rewrite who searched a cell."""
    e = canonical_event(team_id=3)
    with pytest.raises(ValidationError):
        e.team_id = 9


@pytest.mark.parametrize(
    "field,bad",
    [("responder_id", MAX_RESPONDER_ID + 1), ("team_id", MAX_TEAM_ID + 1),
     ("agency_id", MAX_AGENCY_ID + 1), ("responder_id", -1)],
)
def test_attribution_ranges_follow_the_wire_schema(raw_event, field, bad):
    with pytest.raises(ValidationError):
        CanonicalEvent(**(raw_event() | {field: bad}))


def test_both_timestamps_are_retained_for_audit(canonical_event):
    """t_dev for audit, t_srv for display — docs/08 Part 8."""
    e = canonical_event()
    assert e.t_dev is not None
    assert e.t_srv is not None
    assert e.t_dev != e.t_srv


def test_uncommitted_event_has_no_server_fields(load_shared_fixture):
    e = CanonicalEvent(**load_shared_fixture("offline_event_uncommitted.json"))
    assert e.server_seq is None and e.t_srv is None and e.received_via is None
    assert not e.is_committed
    # attribution is complete even before the server has seen it
    assert all(getattr(e, f) is not None for f in REQUIRED_ATTRIBUTION)
