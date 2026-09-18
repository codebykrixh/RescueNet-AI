"""Read-side use cases: delta, snapshot, export, diagnostics (8, 9, 12, 13)."""

from __future__ import annotations

import csv
import io

from sqlalchemy import Connection, select

from rescuenet.domain import EntityType, EventType, Grid
from rescuenet.projections import fold_all
from rescuenet.services import errors
from rescuenet.store import max_server_seq, read_entity_history, read_since
from rescuenet.store.codes import ENTITY_TYPE_CODE, EVENT_TYPE_CODE
from rescuenet.store.tables import event as event_table, incident as incident_table

DEFAULT_PAGE = 200
MAX_PAGE = 1000


def _serialise(e) -> dict:
    return {
        "device_id": e.device_id, "seq": e.seq, "type": e.type.value,
        "entity_type": e.entity_type.value, "entity_id": e.entity_id,
        "payload": e.payload,
        "t_dev": e.t_dev.isoformat() if e.t_dev else None,
        "responder_id": e.responder_id, "team_id": e.team_id,
        "agency_id": e.agency_id, "incident_id": e.incident_id,
        "schema_version": e.schema_version, "server_seq": e.server_seq,
        "t_srv": e.t_srv.isoformat() if e.t_srv else None,
        "received_via": e.received_via.value if e.received_via else None,
    }


def delta(conn: Connection, *, since: int = 0, limit: int = DEFAULT_PAGE,
          entity_type: str | None = None, entity_id: int | None = None,
          team_id: int | None = None, event_type: str | None = None) -> dict:
    """Endpoint 8 — delta sync (cursor = ``server_seq``) and audit history.

    The cursor is a plain integer that never expires (AP-06). Device ``seq`` is
    never a cursor; nor is any timestamp or offset.
    """
    if limit < 1 or limit > MAX_PAGE:
        raise errors.unprocessable(
            "INVALID_LIMIT", f"limit must be 1..{MAX_PAGE}", limit=limit)

    if entity_type is not None and entity_id is not None:
        try:
            events = read_entity_history(conn, EntityType(entity_type), entity_id)
        except ValueError as exc:
            raise errors.unprocessable(
                "UNKNOWN_ENTITY_TYPE", f"unknown entity_type {entity_type!r}") from exc
        events = [e for e in events if e.server_seq > since]
    else:
        stmt = select(event_table).where(event_table.c.server_seq > since)
        if team_id is not None:
            stmt = stmt.where(event_table.c.team_id == team_id)
        if event_type is not None:
            try:
                stmt = stmt.where(event_table.c.type == EVENT_TYPE_CODE[EventType(event_type)])
            except ValueError as exc:
                raise errors.unprocessable(
                    "UNKNOWN_TYPE", f"unknown event type {event_type!r}") from exc
        if entity_type is not None:
            try:
                stmt = stmt.where(
                    event_table.c.entity_type == ENTITY_TYPE_CODE[EntityType(entity_type)])
            except ValueError as exc:
                raise errors.unprocessable(
                    "UNKNOWN_ENTITY_TYPE", f"unknown entity_type {entity_type!r}") from exc
        from rescuenet.store.events import _from_row

        events = [_from_row(r) for r in conn.execute(
            stmt.order_by(event_table.c.server_seq).limit(limit + 1))]

    has_more = len(events) > limit
    page = events[:limit]
    current = max_server_seq(conn)
    return {
        "events": [_serialise(e) for e in page],
        "next_since": page[-1].server_seq if page else since,
        "has_more": has_more,
        "current_server_seq": current,
    }


def _grid_for(events, incident_id: int) -> Grid | None:
    for e in events:
        if e.type is EventType.GRID_GENERATED and e.incident_id == incident_id:
            p = e.payload
            return Grid(origin_lat=p["origin_lat"], origin_lon=p["origin_lon"],
                        cell_size_m=p["cell_size_m"], rows=p["rows"],
                        cols=p["cols"], bearing_deg=p.get("bearing_deg", 0.0))
    return None


def snapshot(conn: Connection, incident_id: int, scope: str = "command") -> dict:
    """Endpoint 9 — initial load.

    ``cell_state`` uses **positional arrays** ``[cell_index, status, team_id]``
    rather than objects, and **untouched cells are omitted entirely** (DM-12):
    the grid parameters already describe them.
    """
    if scope not in ("field", "command"):
        raise errors.unprocessable("INVALID_SCOPE", "scope must be field or command")

    if conn.execute(select(incident_table.c.incident_id).where(
            incident_table.c.incident_id == incident_id)).scalar_one_or_none() is None:
        raise errors.not_found("UNKNOWN_INCIDENT",
                               f"incident {incident_id} does not exist")

    events = read_since(conn, 0)
    scoped = [e for e in events if e.incident_id == incident_id]
    p = fold_all(scoped)
    grid = _grid_for(scoped, incident_id)

    body: dict = {
        "current_server_seq": max_server_seq(conn),
        "incident_id": incident_id,
        "grid": None if grid is None else {
            "origin_lat": grid.origin_lat, "origin_lon": grid.origin_lon,
            "cell_size_m": grid.cell_size_m, "rows": grid.rows,
            "cols": grid.cols, "bearing_deg": grid.bearing_deg,
        },
        "teams": [
            {"team_id": t.team_id, "callsign": t.callsign,
             "agency_id": t.agency_id, "status": t.status}
            for t in p.team_state.values()
        ],
        "cell_state": [
            [s.cell_index, s.status, s.team_id]
            for (_, _), s in sorted(p.cell_state.items())
        ],
    }

    if scope == "command":
        body["duplicate_search"] = [
            {"cell_index": d.cell_index, "team_ids": list(d.team_ids),
             "team_count": d.team_count}
            for d in p.duplicate_search.values()
        ]
        body["team_position"] = [
            {"team_id": t.team_id, "rel_lat": t.rel_lat, "rel_lon": t.rel_lon,
             "t_srv": t.t_srv.isoformat() if t.t_srv else None}
            for t in p.team_position.values()
        ]
        body["survivor_report"] = [
            {"device_id": s.device_id, "seq": s.seq, "cell_index": s.cell_index,
             "person_count": s.person_count, "survivor_status": s.survivor_status,
             "triage": s.triage, "team_id": s.team_id, "agency_id": s.agency_id}
            for s in p.survivor_reports
        ]
        cm = p.coverage_metrics.get(incident_id)
        body["coverage_metrics"] = None if cm is None else {
            "total": cm.total, "searched": cm.searched,
            "in_progress": cm.in_progress, "needs_research": cm.needs_research,
            "assigned": cm.assigned, "unsearched": cm.unsearched,
        }
        body["resource_stock"] = [
            {"team_id": team, "item_id": item, "qty": qty}
            for (team, item), qty in sorted(p.resource_stock.items())
        ]
    return body


def export(conn: Connection, incident_id: int, fmt: str) -> tuple[str, str]:
    """Endpoint 12 — GeoJSON or CSV of grid status and survivor reports."""
    if fmt not in ("geojson", "csv"):
        raise errors.unprocessable("INVALID_FORMAT", "format must be geojson or csv")

    if conn.execute(select(incident_table.c.incident_id).where(
            incident_table.c.incident_id == incident_id)).scalar_one_or_none() is None:
        raise errors.not_found("UNKNOWN_INCIDENT",
                               f"incident {incident_id} does not exist")

    scoped = [e for e in read_since(conn, 0) if e.incident_id == incident_id]
    p = fold_all(scoped)
    grid = _grid_for(scoped, incident_id)

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["cell_index", "label", "status", "team_id"])
        for (_, _), s in sorted(p.cell_state.items()):
            label = grid.cell_label(s.cell_index) if grid else ""
            w.writerow([s.cell_index, label, s.status, s.team_id if s.team_id is not None else ""])
        w.writerow([])
        w.writerow(["device_id", "seq", "cell_index", "person_count",
                    "survivor_status", "triage", "team_id", "agency_id"])
        for s in p.survivor_reports:
            w.writerow([s.device_id, s.seq, s.cell_index, s.person_count,
                        s.survivor_status, s.triage or "", s.team_id, s.agency_id])
        return buf.getvalue(), "text/csv"

    features = []
    for (_, _), s in sorted(p.cell_state.items()):
        props = {"cell_index": s.cell_index, "status": s.status, "team_id": s.team_id}
        geometry = None
        if grid is not None:
            props["label"] = grid.cell_label(s.cell_index)
            corners = grid.cell_corners_local(s.cell_index)
            ring = [[x, y] for x, y in corners] + [[corners[0][0], corners[0][1]]]
            geometry = {"type": "Polygon", "coordinates": [ring]}
        features.append({"type": "Feature", "properties": props, "geometry": geometry})

    for s in p.survivor_reports:
        features.append({
            "type": "Feature",
            "properties": {
                "kind": "survivor_report", "device_id": s.device_id, "seq": s.seq,
                "cell_index": s.cell_index, "person_count": s.person_count,
                "survivor_status": s.survivor_status, "triage": s.triage,
                "team_id": s.team_id, "agency_id": s.agency_id,
            },
            "geometry": None,
        })

    import json

    return json.dumps({"type": "FeatureCollection", "features": features}), "application/geo+json"


def diagnostics(conn: Connection) -> dict:
    """Endpoint 13 — sync diagnostics (T-19, EC-01 evidence)."""
    from sqlalchemy import func

    from rescuenet.projections import watermark
    from rescuenet.store.codes import RECEIVED_VIA_BY_CODE

    total = conn.execute(select(func.count()).select_from(event_table)).scalar_one()
    by_transport = {
        (RECEIVED_VIA_BY_CODE[code].value if code in RECEIVED_VIA_BY_CODE else "UNKNOWN"): n
        for code, n in conn.execute(
            select(event_table.c.received_via, func.count())
            .group_by(event_table.c.received_via)
        )
    }
    current = max_server_seq(conn)
    projected = watermark(conn)
    return {
        "current_server_seq": current,
        "events_total": total,
        "events_by_transport": by_transport,
        "projection_lag": current - projected,
        "mqtt_connected": False,
        "last_publish_server_seq": None,
    }
