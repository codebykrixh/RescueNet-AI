"""Every shared fixture parses into the canonical model (docs/12 M2 criteria)."""
from __future__ import annotations

import json

import pytest

from rescuenet.domain import CanonicalEvent, EventType

pytestmark = pytest.mark.unit

CANONICAL_FIELDS = set(CanonicalEvent.model_fields)


def _events(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def test_fixture_directory_is_populated(all_fixture_files):
    assert all_fixture_files, "shared/fixtures must hold canonical events"


def test_every_fixture_parses(all_fixture_files):
    for path in all_fixture_files:
        for raw in _events(path):
            CanonicalEvent(**raw)


def test_no_fixture_contains_a_field_outside_docs08(all_fixture_files):
    for path in all_fixture_files:
        for raw in _events(path):
            extra = set(raw) - CANONICAL_FIELDS
            assert not extra, f"{path.name} has non-canonical fields {extra}"


def test_fixtures_cover_all_eleven_event_types(all_fixture_files):
    seen = {raw["type"] for p in all_fixture_files for raw in _events(p)}
    assert seen == {t.value for t in EventType}


def test_fixtures_round_trip_through_the_model(all_fixture_files):
    """Parse → dump → parse yields an identical event."""
    for path in all_fixture_files:
        for raw in _events(path):
            once = CanonicalEvent(**raw)
            twice = CanonicalEvent(**once.model_dump(mode="json"))
            assert once == twice, path.name


def test_duplicate_search_fixture_is_two_teams_on_one_cell(load_shared_fixture):
    """D-01b — both events preserved, different identities, same cell."""
    events = [CanonicalEvent(**r)
              for r in load_shared_fixture("duplicate_search_scenario.json")]
    assert len(events) == 2
    assert len({e.identity for e in events}) == 2
    assert len({e.team_id for e in events}) == 2
    assert {e.typed_payload().cell_index for e in events} == {214}


def test_backend_holds_no_duplicate_fixture_copies():
    """F-13 — one canonical location only."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    strays = [p for p in backend.rglob("*.json")
              if "fixture" in str(p).lower() and ".venv" not in str(p)]
    assert not strays, f"canonical fixtures must live in shared/: {strays}"
