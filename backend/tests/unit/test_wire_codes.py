"""Wire codes are permanent (docs/08 DM-33). This test locks them.

Reusing or renumbering a code would make already-stored rows unreadable, so the
values are pinned here deliberately: a change to the mapping must fail loudly.
"""
from __future__ import annotations

import pytest

from rescuenet.domain.enums import EntityType, EventType, ReceivedVia
from rescuenet.store.codes import (
    ENTITY_TYPE_BY_CODE, ENTITY_TYPE_CODE, EVENT_TYPE_BY_CODE, EVENT_TYPE_CODE,
    RECEIVED_VIA_BY_CODE, RECEIVED_VIA_CODE,
)

pytestmark = pytest.mark.unit


def test_event_type_codes_are_pinned():
    """Locks the values chosen during M3.

    The numbers follow the row order of docs/08 §2.1/§2.2, but that ``#`` column
    is a row counter, not a declared wire code — the mapping is unratified (see
    ``store/codes.py``). Pinning it here means any change fails loudly rather
    than silently orphaning stored rows under DM-33.
    """
    assert {t.value: c for t, c in EVENT_TYPE_CODE.items()} == {
        "INCIDENT_DECLARED": 1, "GRID_GENERATED": 2, "TEAM_REGISTERED": 3,
        "DEVICE_ENROLLED": 4, "ASSIGNMENT_ISSUED": 5, "ASSIGNMENT_REVOKED": 6,
        "CELL_STATUS_REPORTED": 7, "SURVIVOR_REPORTED": 8,
        "RESOURCE_DELTA_REPORTED": 9, "POSITION_REPORTED": 10,
        "TEAM_STATUS_REPORTED": 11,
    }


def test_entity_type_codes_are_pinned():
    """Locks the values ratified in docs/08 §14.1 (DM-41).

    ``entity_type`` is persisted but never transmitted independently, so a change
    needs a data migration rather than a wire change — but it is still contract,
    and contract without a test is not enforced.
    """
    assert {e.value: c for e, c in ENTITY_TYPE_CODE.items()} == {
        "CELL": 1, "TEAM": 2, "SURVIVOR": 3, "RESOURCE": 4,
        "INCIDENT": 5, "GRID": 6, "DEVICE": 7, "ASSIGNMENT": 8,
    }


def test_received_via_codes_are_pinned():
    """Locks the values ratified in docs/08 §14.1 (DM-41). Server-set, persisted."""
    assert {r.value: c for r, c in RECEIVED_VIA_CODE.items()} == {
        "INTERNET": 1, "SMS": 2,
    }


def test_every_event_type_has_a_code():
    assert set(EVENT_TYPE_CODE) == set(EventType)
    assert set(ENTITY_TYPE_CODE) == set(EntityType)
    assert set(RECEIVED_VIA_CODE) == set(ReceivedVia)


def test_codes_are_unique():
    for mapping in (EVENT_TYPE_CODE, ENTITY_TYPE_CODE, RECEIVED_VIA_CODE):
        assert len(set(mapping.values())) == len(mapping)


def test_codes_round_trip():
    for member, code in EVENT_TYPE_CODE.items():
        assert EVENT_TYPE_BY_CODE[code] is member
    for member, code in ENTITY_TYPE_CODE.items():
        assert ENTITY_TYPE_BY_CODE[code] is member
    for member, code in RECEIVED_VIA_CODE.items():
        assert RECEIVED_VIA_BY_CODE[code] is member


def test_event_type_codes_fit_the_four_bit_wire_field():
    """DM-01 widened the field to 4 bits for 11 types."""
    assert max(EVENT_TYPE_CODE.values()) < 2**4
