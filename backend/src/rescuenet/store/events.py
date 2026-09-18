"""Event persistence: append, deduplicate, read (docs/08 Parts 5, 8, 11).

Ingestion is idempotent **by construction**: ``(device_id, seq)`` is the primary
key and inserts use ``ON CONFLICT DO NOTHING`` (AD-28, DM-06). A repeat is
reported as accepted, carrying the ``server_seq`` the event already has.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Connection, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from rescuenet.domain.enums import EntityType, EventType, ReceivedVia
from rescuenet.domain.event import CanonicalEvent
from rescuenet.store.codes import (
    ENTITY_TYPE_BY_CODE,
    ENTITY_TYPE_CODE,
    EVENT_TYPE_BY_CODE,
    EVENT_TYPE_CODE,
    RECEIVED_VIA_BY_CODE,
    RECEIVED_VIA_CODE,
)
from rescuenet.store.tables import event as event_table


@dataclass(frozen=True)
class AppendResult:
    """Outcome of appending one event."""

    device_id: int
    seq: int
    server_seq: int
    was_duplicate: bool


def _to_row(e: CanonicalEvent, received_via: ReceivedVia | None) -> dict:
    via = received_via if received_via is not None else e.received_via
    return {
        "device_id": e.device_id,
        "seq": e.seq,
        "incident_id": e.incident_id,
        "type": EVENT_TYPE_CODE[e.type],
        "entity_type": ENTITY_TYPE_CODE[e.entity_type],
        "entity_id": e.entity_id,
        "payload": e.payload,
        "t_dev": e.t_dev,
        "schema_version": e.schema_version,
        "responder_id": e.responder_id,
        "team_id": e.team_id,
        "agency_id": e.agency_id,
        "received_via": RECEIVED_VIA_CODE[via] if via is not None else None,
    }


def _from_row(row) -> CanonicalEvent:
    m = row._mapping
    via = m["received_via"]
    return CanonicalEvent(
        device_id=m["device_id"],
        seq=m["seq"],
        type=EVENT_TYPE_BY_CODE[m["type"]],
        entity_type=ENTITY_TYPE_BY_CODE[m["entity_type"]],
        entity_id=m["entity_id"],
        payload=m["payload"],
        t_dev=m["t_dev"],
        responder_id=m["responder_id"],
        team_id=m["team_id"],
        agency_id=m["agency_id"],
        incident_id=m["incident_id"],
        schema_version=m["schema_version"],
        server_seq=m["server_seq"],
        t_srv=m["t_srv"],
        received_via=RECEIVED_VIA_BY_CODE[via] if via is not None else None,
    )


def append(
    conn: Connection,
    canonical: CanonicalEvent,
    *,
    received_via: ReceivedVia | None = None,
) -> AppendResult:
    """Append one event. Idempotent on ``(device_id, seq)``.

    A duplicate is **accepted**, not rejected (AD-28): the caller is told the
    original ``server_seq`` and that it was a repeat.
    """
    stmt = (
        pg_insert(event_table)
        .values(**_to_row(canonical, received_via))
        .on_conflict_do_nothing(index_elements=["device_id", "seq"])
        .returning(event_table.c.server_seq)
    )
    inserted = conn.execute(stmt).scalar_one_or_none()
    if inserted is not None:
        return AppendResult(canonical.device_id, canonical.seq, inserted, False)

    existing = conn.execute(
        select(event_table.c.server_seq).where(
            event_table.c.device_id == canonical.device_id,
            event_table.c.seq == canonical.seq,
        )
    ).scalar_one()
    return AppendResult(canonical.device_id, canonical.seq, existing, True)


def append_many(
    conn: Connection,
    events: list[CanonicalEvent],
    *,
    received_via: ReceivedVia | None = None,
) -> list[AppendResult]:
    return [append(conn, e, received_via=received_via) for e in events]


def read_since(conn: Connection, since_server_seq: int = 0, limit: int | None = None):
    """Events with ``server_seq`` greater than the watermark, in order."""
    stmt = (
        select(event_table)
        .where(event_table.c.server_seq > since_server_seq)
        .order_by(event_table.c.server_seq)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return [_from_row(r) for r in conn.execute(stmt)]


def read_entity_history(conn: Connection, entity_type: EntityType, entity_id: int):
    """Every event touching one entity, ordered — the audit query (docs/08 §13.2)."""
    stmt = (
        select(event_table)
        .where(
            event_table.c.entity_type == ENTITY_TYPE_CODE[entity_type],
            event_table.c.entity_id == entity_id,
        )
        .order_by(event_table.c.server_seq)
    )
    return [_from_row(r) for r in conn.execute(stmt)]


def max_server_seq(conn: Connection) -> int:
    from sqlalchemy import func

    return conn.execute(
        select(func.coalesce(func.max(event_table.c.server_seq), 0))
    ).scalar_one()


def count(conn: Connection) -> int:
    from sqlalchemy import func

    return conn.execute(select(func.count()).select_from(event_table)).scalar_one()
