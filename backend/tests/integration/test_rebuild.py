"""M3 rebuild-from-empty and read-model derivation (AD-27, DM-30, TR-29)."""
from __future__ import annotations

import pytest
from sqlalchemy import select, text

from rescuenet.domain import CanonicalEvent
from rescuenet.projections import clear_read_models, rebuild, watermark
from rescuenet.store import append, connection, max_server_seq
from rescuenet.store.tables import (
    cell_state, coverage_metrics, duplicate_search, resource_stock, survivor_report,
)

pytestmark = pytest.mark.integration


def _seed(conn, raw_event, load_shared_fixture):
    """The D-01b scenario plus a grid, inventory and a survivor report."""
    grid = CanonicalEvent(**raw_event(
        device_id=0, seq=2, type="GRID_GENERATED", entity_type="GRID", entity_id=9,
        team_id=0, payload={"origin_lat": 0.0, "origin_lon": 0.0, "cell_size_m": 100.0,
                            "rows": 10, "cols": 10, "bearing_deg": 0.0}))
    alpha = CanonicalEvent(**raw_event(device_id=17, seq=4021))                   # team 3
    bravo = CanonicalEvent(**raw_event(device_id=22, seq=951, team_id=5,
                                       agency_id=2, responder_id=84))              # team 5
    survivor = CanonicalEvent(**load_shared_fixture("survivor_reported.json"))
    stock = CanonicalEvent(**load_shared_fixture("resource_delta_reported.json"))
    for e in (grid, alpha, bravo, survivor, stock):
        append(conn, e)


def test_rebuild_from_empty_produces_expected_state(clean_db, app_engine, raw_event,
                                                    load_shared_fixture):
    with connection(app_engine) as conn:
        _seed(conn, raw_event, load_shared_fixture)
        rebuild(conn)

        cells = conn.execute(select(cell_state)).mappings().all()
        assert any(c["cell_index"] == 214 and c["status"] == "SEARCHED" for c in cells)

        dupes = conn.execute(select(duplicate_search)).mappings().all()
        assert len(dupes) == 1 and dupes[0]["cell_index"] == 214
        assert sorted(dupes[0]["team_ids"]) == [3, 5], "both agencies named"

        assert conn.execute(select(survivor_report)).rowcount != 0
        assert conn.execute(
            select(resource_stock.c.qty)).scalar_one() == -2

        m = conn.execute(select(coverage_metrics)).mappings().one()
        assert m["total"] == 100 and m["searched"] == 1 and m["unsearched"] == 99


def test_rebuild_is_deterministic_across_destroy_and_replay(clean_db, app_engine,
                                                            raw_event,
                                                            load_shared_fixture):
    """Destroy the read models, replay, obtain identical state (AD-27)."""
    def snapshot(conn):
        return {
            "cells": conn.execute(select(cell_state).order_by(
                cell_state.c.incident_id, cell_state.c.cell_index)).mappings().all(),
            "dupes": conn.execute(select(duplicate_search)).mappings().all(),
            "stock": conn.execute(select(resource_stock)).mappings().all(),
            "cover": conn.execute(select(coverage_metrics)).mappings().all(),
        }

    with connection(app_engine) as conn:
        _seed(conn, raw_event, load_shared_fixture)
        rebuild(conn)
        first = snapshot(conn)

    with connection(app_engine) as conn:
        clear_read_models(conn)
        assert conn.execute(select(cell_state)).first() is None, "read models destroyed"

    with connection(app_engine) as conn:
        rebuild(conn)
        second = snapshot(conn)

    assert first == second


def test_rebuild_does_not_touch_the_event_log(clean_db, app_engine, raw_event,
                                              load_shared_fixture):
    with connection(app_engine) as conn:
        _seed(conn, raw_event, load_shared_fixture)
        before = max_server_seq(conn)
        n_before = conn.execute(text("select count(*) from event")).scalar_one()
        rebuild(conn)
        rebuild(conn)
        assert max_server_seq(conn) == before
        assert conn.execute(text("select count(*) from event")).scalar_one() == n_before


def test_rebuild_on_an_empty_log_is_a_no_op(clean_db, app_engine):
    with connection(app_engine) as conn:
        rebuild(conn)
        assert conn.execute(select(cell_state)).first() is None
        assert watermark(conn) == 0


def test_watermark_tracks_the_log(clean_db, app_engine, raw_event, load_shared_fixture):
    with connection(app_engine) as conn:
        _seed(conn, raw_event, load_shared_fixture)
        rebuild(conn)
        assert watermark(conn) == max_server_seq(conn)


def test_event_log_remains_the_source_of_truth(clean_db, app_engine, raw_event,
                                               load_shared_fixture):
    """Read models are disposable; the log is not."""
    with connection(app_engine) as conn:
        _seed(conn, raw_event, load_shared_fixture)
        rebuild(conn)
        clear_read_models(conn)
        assert conn.execute(text("select count(*) from event")).scalar_one() == 5
        rebuild(conn)
        assert conn.execute(select(duplicate_search)).mappings().all()
