"""Assignment use cases (endpoints 10, 11)."""

from __future__ import annotations

from sqlalchemy import Connection, func, select

from rescuenet.domain import EventType
from rescuenet.domain.limits import MAX_CELL_INDEX
from rescuenet.projections import fold_assignment_state
from rescuenet.services import errors, server_events
from rescuenet.store import read_since
from rescuenet.store.tables import event as event_table


def _next_assignment_id(conn: Connection) -> int:
    highest = conn.execute(
        select(func.coalesce(func.max(event_table.c.entity_id), 0)).where(
            event_table.c.type == 5  # ASSIGNMENT_ISSUED, docs/08 §14.1
        )
    ).scalar_one()
    return highest + 1


def issue(conn: Connection, body: dict, incident_id: int) -> dict:
    """Endpoint 10 — issue an assignment.

    AP-03: a cell already held by another team returns **201 with
    ``already_held``**, not 409. FR-303 requires the collision to be *surfaced*,
    not to block the commander.
    """
    for cell in body["cell_ids"]:
        if not 0 <= cell <= MAX_CELL_INDEX:
            raise errors.unprocessable(
                "UNKNOWN_CELL", f"cell_index {cell} outside 0..{MAX_CELL_INDEX}",
                cell_index=cell,
            )

    holders = fold_assignment_state(read_since(conn, 0))
    already_held = [
        {"cell_index": cell, "team_id": holders[(incident_id, cell)].team_id}
        for cell in body["cell_ids"]
        if (incident_id, cell) in holders
        and holders[(incident_id, cell)].team_id is not None
        and holders[(incident_id, cell)].team_id != body["team_id"]
    ]

    assignment_id = _next_assignment_id(conn)
    payload = {
        "assignment_id": assignment_id,
        "team_id": body["team_id"],
        "cell_ids": list(body["cell_ids"]),
    }
    if body.get("note") is not None:
        payload["note"] = body["note"]

    _, result = server_events.author(
        conn, event_type=EventType.ASSIGNMENT_ISSUED, entity_id=assignment_id,
        payload=payload, incident_id=incident_id,
    )
    return {
        "assignment_id": assignment_id,
        "server_seq": result.server_seq,
        "already_held": already_held,
    }


def revoke(conn: Connection, assignment_id: int, reason: str | None = None) -> dict:
    """Endpoint 11 — revoke an assignment."""
    issued = [
        e for e in read_since(conn, 0)
        if e.type is EventType.ASSIGNMENT_ISSUED
        and e.payload.get("assignment_id") == assignment_id
    ]
    if not issued:
        raise errors.not_found(
            "UNKNOWN_ASSIGNMENT", f"assignment {assignment_id} does not exist",
            assignment_id=assignment_id,
        )

    payload = {"assignment_id": assignment_id}
    if reason is not None:
        payload["reason"] = reason
    _, result = server_events.author(
        conn, event_type=EventType.ASSIGNMENT_REVOKED, entity_id=assignment_id,
        payload=payload, incident_id=issued[0].incident_id,
    )
    return {"server_seq": result.server_seq}
