"""**TR-11** and **TR-12**, Python side — ``docs/11``, both are "JUnit5 + pytest".

TR-11 is **release-blocking** and traces audit finding **F-01**: the 13-bit
``cell_index`` field and ``MAX_CELLS`` must never drift apart again.
"""

from __future__ import annotations

import pytest

from rescuenet.codec import BitWriter, encode_payload, event_bits
from rescuenet.codec import wire
from rescuenet.domain.enums import EventType
from rescuenet.domain.limits import MAX_CELL_INDEX, MAX_CELLS, RESERVED_CELL_INDEX


def _header(count: int = 1) -> dict:
    return {
        "proto_version": 1, "device_id": 17, "team_id": 3, "agency_id": 1,
        "incident_id": 9, "schema_version": 1, "base_seq": 4021,
        "base_t": 3600, "event_count": count,
    }


def _cell(idx: int, seq_delta: int = 0) -> dict:
    return {
        "type": EventType.CELL_STATUS_REPORTED, "seq_delta": seq_delta, "t_delta": 0,
        "responder_id": 71, "payload": {"cell_index": idx, "status": "SEARCHED"},
    }


# ─────────────────────────────── TR-11 ───────────────────────────────

def test_tr11_cell_index_field_is_13_bits_and_bounds_agree():
    """The width and the domain cap are one fact, not two (F-01)."""
    assert wire.CELL_INDEX_BITS == 13
    assert MAX_CELLS == 8191
    assert MAX_CELL_INDEX == 8190
    assert RESERVED_CELL_INDEX == 8191
    assert (1 << wire.CELL_INDEX_BITS) - 1 == RESERVED_CELL_INDEX


def test_tr11_every_valid_cell_index_packs_distinctly():
    """0…8,190 must each produce a distinct encoding — no wrap, no collision."""
    seen: dict[bytes, int] = {}
    for idx in range(0, MAX_CELL_INDEX + 1):
        packed = encode_payload(_header(), [_cell(idx)])
        assert packed not in seen, f"collision: {idx} and {seen.get(packed)}"
        seen[packed] = idx
    assert len(seen) == 8191


def test_tr11_index_8192_is_refused_not_truncated():
    """One past the field width must raise, never silently wrap to 0."""
    with pytest.raises(ValueError):
        encode_payload(_header(), [_cell(8192)])


def test_tr11_reserved_index_8191_still_fits_the_field_but_is_not_a_valid_cell():
    """8,191 is representable in 13 bits yet never allocated (docs/09 §10.5)."""
    encode_payload(_header(), [_cell(RESERVED_CELL_INDEX)])   # fits the field
    assert RESERVED_CELL_INDEX > MAX_CELL_INDEX               # but is not a valid cell


# ─────────────────────────────── TR-12 ───────────────────────────────

def test_tr12_grid_generated_has_no_sms_layout():
    """DM-10: the grid is one parametric event, and it is not SMS-eligible (SCOPE A)."""
    assert EventType.GRID_GENERATED not in wire.SMS_ELIGIBLE
    with pytest.raises(wire.WireEncodingError):
        wire.pack_event(BitWriter(), EventType.GRID_GENERATED, 0, 0, 1, {})


@pytest.mark.parametrize("rows,cols", [(1, 1), (25, 200), (89, 92), (1, 8191)])
def test_tr12_parametric_grid_indices_all_fit_the_wire_field(rows, cols):
    """Every index a parametric grid can produce must be addressable."""
    cells = rows * cols
    assert cells <= MAX_CELLS
    assert cells - 1 <= MAX_CELL_INDEX


def test_tr12_only_the_four_scope_a_types_are_sms_eligible():
    assert wire.SMS_ELIGIBLE == frozenset({
        EventType.CELL_STATUS_REPORTED, EventType.SURVIVOR_REPORTED,
        EventType.RESOURCE_DELTA_REPORTED, EventType.TEAM_STATUS_REPORTED,
    })
    assert EventType.POSITION_REPORTED not in wire.SMS_ELIGIBLE


# ───────────────────── layout and cross-language lock ─────────────────

def test_header_is_89_bits():
    w = BitWriter()
    wire.pack_header(w, _header())
    assert w.bit_length == 89 == wire.HEADER_BITS


@pytest.mark.parametrize("etype,payload,expected", [
    (EventType.CELL_STATUS_REPORTED, {"cell_index": 1, "status": "SEARCHED"}, 48),
    (EventType.RESOURCE_DELTA_REPORTED, {"item_id": 1, "qty_delta": -1}, 48),
    (EventType.TEAM_STATUS_REPORTED, {"team_status": "ACTIVE"}, 35),
    (EventType.SURVIVOR_REPORTED,
     {"cell_index": 1, "person_count": 1, "survivor_status": "TRAPPED"}, 57),
    (EventType.SURVIVOR_REPORTED,
     {"cell_index": 1, "person_count": 1, "survivor_status": "TRAPPED",
      "triage": "RED", "rel_lat": 1, "rel_lon": 1}, 92),
])
def test_event_bit_lengths_match_the_ratified_contract(etype, payload, expected):
    assert event_bits(etype, payload) == expected


def test_cross_language_vector_matches_the_kotlin_codec():
    """The Kotlin suite asserts this exact hex. Either side drifting fails both."""
    packed = encode_payload(_header(), [_cell(214)])
    assert packed.hex() == "1011031009100fb500e100b800000d622380"


def test_budget_arithmetic():
    assert wire.FIXED_OVERHEAD_BITS == 157
    assert wire.EVENT_CAPACITY_BITS == 803
    assert wire.EVENT_CAPACITY_BITS // 35 == 22
    assert wire.EVENT_CAPACITY_BITS // 48 == 16
    assert wire.EVENT_CAPACITY_BITS // 92 == 8


def test_signed_fields_round_trip_through_two_complement():
    for qty in (-128, -1, 0, 127):
        encode_payload(_header(), [{
            "type": EventType.RESOURCE_DELTA_REPORTED, "seq_delta": 0, "t_delta": 0,
            "responder_id": 71, "payload": {"item_id": 7, "qty_delta": qty},
        }])
    with pytest.raises(ValueError):
        encode_payload(_header(), [{
            "type": EventType.RESOURCE_DELTA_REPORTED, "seq_delta": 0, "t_delta": 0,
            "responder_id": 71, "payload": {"item_id": 7, "qty_delta": 128},
        }])


def test_events_must_ascend_by_seq():
    with pytest.raises(wire.WireEncodingError):
        encode_payload(_header(2), [_cell(1, seq_delta=5), _cell(2, seq_delta=3)])


def test_never_truncates_out_of_range_deltas():
    with pytest.raises(ValueError):
        encode_payload(_header(), [_cell(1, seq_delta=64)])       # 6-bit
    with pytest.raises(ValueError):
        encode_payload(_header(), [{**_cell(1), "t_delta": 4096}])  # 12-bit


# ─────────────── incident epoch: mobile and backend must agree ───────────────

def test_incident_epoch_naive_timestamps_are_read_as_utc():
    """``base_t`` is derived from this on both sides; a timezone disagreement
    would fail every MAC. The device's ``IncidentEpoch`` does the same."""
    from rescuenet.services.batch_mac import _to_epoch_seconds

    forms = [
        "2026-08-22T09:00:00+00:00",
        "2026-08-22T09:00:00Z",
        "2026-08-22T09:00:00",       # naive — must be UTC, not local
    ]
    results = {_to_epoch_seconds(v) for v in forms}
    assert len(results) == 1, f"all three forms must agree, got {results}"
    assert results.pop() == 1787389200


def test_incident_epoch_accepts_datetime_and_epoch_inputs():
    from datetime import datetime, timezone

    from rescuenet.services.batch_mac import _to_epoch_seconds

    aware = datetime(2026, 8, 22, 9, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 8, 22, 9, 0, 0)
    assert _to_epoch_seconds(aware) == _to_epoch_seconds(naive) == 1787389200
    assert _to_epoch_seconds(1787389200) == 1787389200
    assert _to_epoch_seconds(1787389200000) == 1787389200
