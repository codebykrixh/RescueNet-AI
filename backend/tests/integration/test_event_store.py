"""M3 event store against live PostgreSQL: TR-08, TR-30, server_seq, TR-32."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from rescuenet.domain import CanonicalEvent, EntityType, ReceivedVia
from rescuenet.store import append, connection, count, read_entity_history, read_since

pytestmark = pytest.mark.integration


# ─────────────────────────── TR-08 · idempotency ────────────────────────────
def test_first_insert_succeeds(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        r = append(conn, canonical_event())
        assert r.was_duplicate is False and r.server_seq > 0
        assert count(conn) == 1


def test_identical_duplicate_is_idempotent(clean_db, app_engine, canonical_event):
    e = canonical_event()
    with connection(app_engine) as conn:
        first = append(conn, e)
    with connection(app_engine) as conn:
        second = append(conn, e)
        assert second.was_duplicate is True
        assert second.server_seq == first.server_seq, "must keep the original server_seq"
        assert count(conn) == 1, "no second row"


def test_different_content_same_identity_does_not_overwrite(clean_db, app_engine,
                                                            raw_event):
    """docs/08 DM-31/AD-28: the first write wins; the second is a no-op no-error."""
    original = CanonicalEvent(**raw_event(payload={"cell_index": 214,
                                                   "status": "SEARCHED"}))
    impostor = CanonicalEvent(**raw_event(payload={"cell_index": 214,
                                                   "status": "IN_PROGRESS"}))
    with connection(app_engine) as conn:
        append(conn, original)
    with connection(app_engine) as conn:
        result = append(conn, impostor)
        assert result.was_duplicate is True
        stored = read_since(conn, 0)
        assert len(stored) == 1
        assert stored[0].payload["status"] == "SEARCHED", "original content preserved"


def test_distinct_sequences_persist_independently(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        append(conn, canonical_event(seq=1))
        append(conn, canonical_event(seq=2))
        append(conn, canonical_event(device_id=22, seq=1))
        assert count(conn) == 3


def test_two_devices_same_seq_are_two_events(clean_db, app_engine, canonical_event):
    """DM-15 — the duplicate-search case: same action, two devices, two facts."""
    with connection(app_engine) as conn:
        a = append(conn, canonical_event(device_id=17, seq=4021))
        b = append(conn, canonical_event(device_id=22, seq=4021))
        assert a.server_seq != b.server_seq
        assert count(conn) == 2


# ─────────────────────────── server_seq ─────────────────────────────────────
def test_server_seq_is_monotonic_in_arrival_order(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        seqs = [append(conn, canonical_event(device_id=d, seq=s)).server_seq
                for d, s in [(17, 1), (22, 1), (17, 2), (31, 9)]]
    assert seqs == sorted(seqs) and len(set(seqs)) == 4


def test_server_seq_is_independent_of_device_clock(clean_db, app_engine, canonical_event):
    """AL-05 — acceptance order, not occurrence order (DM-21)."""
    late = canonical_event(device_id=17, seq=1, t_dev="2026-08-22T10:00:00Z")
    early = canonical_event(device_id=22, seq=1, t_dev="2026-08-22T09:00:00Z")
    with connection(app_engine) as conn:
        first = append(conn, late)     # older t_dev, arrives first
        second = append(conn, early)   # newer? no — earlier t_dev, arrives second
    assert first.server_seq < second.server_seq
    assert late.t_dev > early.t_dev, "arrival order deliberately inverts device time"


def test_server_seq_is_not_the_identity(clean_db, app_engine, canonical_event):
    e = canonical_event()
    with connection(app_engine) as conn:
        append(conn, e)
        stored = read_since(conn, 0)[0]
    assert stored.identity == e.identity
    assert stored.server_seq is not None and stored.server_seq != e.seq


def test_read_since_returns_only_later_events(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        a = append(conn, canonical_event(seq=1))
        append(conn, canonical_event(seq=2))
        assert [e.seq for e in read_since(conn, a.server_seq)] == [2]


# ──────────────────── TR-30 · append-only, enforced by the database ─────────
def test_app_role_cannot_update_event(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        append(conn, canonical_event())
    with pytest.raises(ProgrammingError) as err:
        with connection(app_engine) as conn:
            conn.execute(text("UPDATE event SET team_id = 99"))
    assert "permission denied" in str(err.value).lower()


def test_app_role_cannot_delete_event(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        append(conn, canonical_event())
    with pytest.raises(ProgrammingError) as err:
        with connection(app_engine) as conn:
            conn.execute(text("DELETE FROM event"))
    assert "permission denied" in str(err.value).lower()


def test_app_role_cannot_truncate_event(clean_db, app_engine, canonical_event):
    with pytest.raises(ProgrammingError):
        with connection(app_engine) as conn:
            conn.execute(text("TRUNCATE TABLE event"))


def test_app_role_can_insert_and_select(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        append(conn, canonical_event())
        assert count(conn) == 1


def test_the_app_really_is_running_as_the_restricted_role(app_engine):
    from rescuenet.store import APP_ROLE, current_role

    with connection(app_engine) as conn:
        assert current_role(conn) == APP_ROLE


def test_read_models_remain_writable(clean_db, app_engine):
    """Read models are disposable, so the restricted role keeps full DML on them."""
    with connection(app_engine) as conn:
        conn.execute(text(
            "INSERT INTO cell_state (incident_id, cell_index, status) "
            "VALUES (9, 1, 'SEARCHED')"))
        conn.execute(text("UPDATE cell_state SET status='IN_PROGRESS'"))
        conn.execute(text("DELETE FROM cell_state"))


# ─────────────────────────── TR-32 · audit reconstruction ───────────────────
def test_audit_history_for_one_cell(clean_db, app_engine, raw_event, load_shared_fixture):
    """'What happened to grid O-2?' answered from `event` alone (docs/08 §13.2)."""
    with connection(app_engine) as conn:
        append(conn, CanonicalEvent(**raw_event(device_id=17, seq=4021)))
        append(conn, CanonicalEvent(**raw_event(device_id=22, seq=951, team_id=5,
                                                agency_id=2, responder_id=84)))
        append(conn, CanonicalEvent(**load_shared_fixture("team_status_reported.json")))

        history = read_entity_history(conn, EntityType.CELL, 214)
    assert len(history) == 2, "only the two cell events"
    assert [e.server_seq for e in history] == sorted(e.server_seq for e in history)
    for e in history:
        assert e.responder_id and e.team_id is not None and e.agency_id is not None
        assert e.t_dev is not None and e.t_srv is not None
    assert {e.team_id for e in history} == {3, 5}, "both agencies attributed"


def test_received_via_round_trips(clean_db, app_engine, canonical_event):
    with connection(app_engine) as conn:
        append(conn, canonical_event(), received_via=ReceivedVia.SMS)
        assert read_since(conn, 0)[0].received_via is ReceivedVia.SMS
