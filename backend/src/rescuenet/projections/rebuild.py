"""Persisting projections and rebuilding them from the log (AD-27, DM-30).

Every read model here is **disposable**. It can be dropped and rebuilt from
``event`` alone, which is simultaneously the audit guarantee, the recovery
mechanism and the schema-migration strategy. The event log remains the only
source of truth (AD-01, AD-04).
"""

from __future__ import annotations

from sqlalchemy import Connection, delete, insert, select

from rescuenet.projections.folds import Projections, fold_all
from rescuenet.store import events as event_store
from rescuenet.store.tables import (
    READ_MODELS,
    assignment_state,
    cell_state,
    coverage_metrics,
    duplicate_search,
    projection_state,
    resource_stock,
    survivor_report,
    team_position,
    team_state,
)

_SINGLETON = 1


def clear_read_models(conn: Connection) -> None:
    """Truncate every read model. The event log is untouched."""
    for table in READ_MODELS:
        conn.execute(delete(table))


def _write(conn: Connection, p: Projections, watermark: int) -> None:
    if p.cell_state:
        conn.execute(insert(cell_state), [
            {"incident_id": s.incident_id, "cell_index": s.cell_index,
             "status": s.status, "team_id": s.team_id,
             "last_server_seq": s.last_server_seq}
            for s in p.cell_state.values()
        ])
    if p.duplicate_search:
        conn.execute(insert(duplicate_search), [
            {"incident_id": d.incident_id, "cell_index": d.cell_index,
             "team_count": d.team_count, "team_ids": list(d.team_ids)}
            for d in p.duplicate_search.values()
        ])
    if p.assignment_state:
        conn.execute(insert(assignment_state), [
            {"incident_id": a.incident_id, "cell_index": a.cell_index,
             "team_id": a.team_id, "assignment_id": a.assignment_id,
             "last_server_seq": a.last_server_seq}
            for a in p.assignment_state.values()
        ])
    if p.team_state:
        conn.execute(insert(team_state), [
            {"team_id": t.team_id, "callsign": t.callsign, "agency_id": t.agency_id,
             "status": t.status, "last_server_seq": t.last_server_seq}
            for t in p.team_state.values()
        ])
    if p.team_position:
        conn.execute(insert(team_position), [
            {"team_id": t.team_id, "rel_lat": t.rel_lat, "rel_lon": t.rel_lon,
             "t_srv": t.t_srv, "last_server_seq": t.last_server_seq}
            for t in p.team_position.values()
        ])
    if p.resource_stock:
        conn.execute(insert(resource_stock), [
            {"team_id": team, "item_id": item, "qty": qty}
            for (team, item), qty in p.resource_stock.items()
        ])
    if p.survivor_reports:
        conn.execute(insert(survivor_report), [
            {"device_id": s.device_id, "seq": s.seq, "incident_id": s.incident_id,
             "cell_index": s.cell_index, "person_count": s.person_count,
             "survivor_status": s.survivor_status, "triage": s.triage,
             "team_id": s.team_id, "agency_id": s.agency_id,
             "unresolved_cell": False, "server_seq": s.server_seq}
            for s in p.survivor_reports
        ])
    if p.coverage_metrics:
        conn.execute(insert(coverage_metrics), [
            {"incident_id": c.incident_id, "total": c.total, "searched": c.searched,
             "in_progress": c.in_progress, "needs_research": c.needs_research,
             "assigned": c.assigned, "unsearched": c.unsearched}
            for c in p.coverage_metrics.values()
        ])
    conn.execute(insert(projection_state).values(
        id=_SINGLETON, last_projected_server_seq=watermark
    ))


def rebuild(conn: Connection) -> Projections:
    """Drop every read model and recompute it from the whole event log.

    Deterministic: the same log always produces the same read models, which is
    what makes AD-27 load-bearing rather than decorative.
    """
    clear_read_models(conn)
    all_events = event_store.read_since(conn, 0)
    projections = fold_all(all_events)
    _write(conn, projections, event_store.max_server_seq(conn))
    return projections


def watermark(conn: Connection) -> int:
    """``last_projected_server_seq``, or 0 when nothing has been projected."""
    value = conn.execute(
        select(projection_state.c.last_projected_server_seq)
        .where(projection_state.c.id == _SINGLETON)
    ).scalar_one_or_none()
    return value or 0
