"""Incident, grid and team use cases (endpoints 3, 4, 5)."""

from __future__ import annotations

from sqlalchemy import Connection, insert, select

from rescuenet.domain import EventType, Grid, GridError
from rescuenet.domain.limits import MAX_CELLS
from rescuenet.services import errors, server_events
from rescuenet.store.tables import incident as incident_table


def declare_incident(conn: Connection, body: dict) -> dict:
    """Endpoint 3 — create the incident row and emit ``INCIDENT_DECLARED``."""
    incident_id = conn.execute(
        insert(incident_table)
        .values(
            name=body["name"],
            disaster_type=body["disaster_type"],
            origin_lat=body["origin_lat"],
            origin_lon=body["origin_lon"],
            started_at=body["started_at"],
            notes=body.get("notes"),
        )
        .returning(incident_table.c.incident_id)
    ).scalar_one()

    payload = {
        "name": body["name"],
        "disaster_type": body["disaster_type"],
        "origin_lat": body["origin_lat"],
        "origin_lon": body["origin_lon"],
        "started_at": body["started_at"].isoformat()
        if hasattr(body["started_at"], "isoformat")
        else body["started_at"],
    }
    if body.get("notes") is not None:
        payload["notes"] = body["notes"]

    _, result = server_events.author(
        conn, event_type=EventType.INCIDENT_DECLARED, entity_id=incident_id,
        payload=payload, incident_id=incident_id,
    )
    return {"incident_id": incident_id, "server_seq": result.server_seq}


def require_incident(conn: Connection, incident_id: int) -> None:
    exists = conn.execute(
        select(incident_table.c.incident_id).where(
            incident_table.c.incident_id == incident_id
        )
    ).scalar_one_or_none()
    if exists is None:
        raise errors.not_found(
            "UNKNOWN_INCIDENT", f"incident {incident_id} does not exist",
            incident_id=incident_id,
        )


def generate_grid(conn: Connection, incident_id: int, body: dict) -> dict:
    """Endpoint 4 — emit ``GRID_GENERATED``. Immutable once published (FR-205)."""
    require_incident(conn, incident_id)

    from rescuenet.store import read_since

    for existing in read_since(conn, 0):
        if existing.type is EventType.GRID_GENERATED and existing.incident_id == incident_id:
            raise errors.conflict(
                "GRID_ALREADY_GENERATED",
                f"incident {incident_id} already has a published grid",
                incident_id=incident_id,
            )

    try:
        Grid(
            origin_lat=body["origin_lat"], origin_lon=body["origin_lon"],
            cell_size_m=body["cell_size_m"], rows=body["rows"], cols=body["cols"],
            bearing_deg=body.get("bearing_deg", 0.0),
        )
    except GridError as exc:
        raise errors.unprocessable(
            "INVALID_GRID", str(exc),
            rows=body["rows"], cols=body["cols"], max_cells=MAX_CELLS,
        ) from exc

    payload = {
        "origin_lat": body["origin_lat"], "origin_lon": body["origin_lon"],
        "cell_size_m": body["cell_size_m"], "rows": body["rows"],
        "cols": body["cols"], "bearing_deg": body.get("bearing_deg", 0.0),
    }
    _, result = server_events.author(
        conn, event_type=EventType.GRID_GENERATED, entity_id=incident_id,
        payload=payload, incident_id=incident_id,
    )
    return {
        "incident_id": incident_id,
        "cell_count": body["rows"] * body["cols"],
        "server_seq": result.server_seq,
    }


def register_team(conn: Connection, body: dict, incident_id: int) -> dict:
    """Endpoint 5 — emit ``TEAM_REGISTERED``."""
    require_incident(conn, incident_id)
    payload = {
        "team_id": body["team_id"], "callsign": body["callsign"],
        "agency_id": body["agency_id"], "agency_type": body["agency_type"],
    }
    _, result = server_events.author(
        conn, event_type=EventType.TEAM_REGISTERED, entity_id=body["team_id"],
        payload=payload, incident_id=incident_id,
    )
    return {"team_id": body["team_id"], "server_seq": result.server_seq}
