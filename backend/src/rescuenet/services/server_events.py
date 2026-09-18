"""Server-authored events (docs/08 DM-36).

Commander intents arrive as REST calls; the **server** authors the corresponding
canonical event under the reserved ``device_id = 0``. The dashboard never
allocates ``(device_id, seq)``.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Connection, func, select

from rescuenet.domain import CanonicalEvent, EntityType, EventType, ReceivedVia
from rescuenet.domain.enums import entity_type_for
from rescuenet.domain.limits import CURRENT_SCHEMA_VERSION, SERVER_DEVICE_ID
from rescuenet.store import append
from rescuenet.store.tables import event as event_table

#: Commander identity used for server-authored events until M5 supplies real
#: session identity. Recorded as transitional in docs/12 §3.2.1.
COMMANDER_RESPONDER_ID = 1
COMMANDER_TEAM_ID = 0
COMMANDER_AGENCY_ID = 1


def next_server_seq(conn: Connection) -> int:
    """Next monotonic ``seq`` for the reserved server device."""
    highest = conn.execute(
        select(func.coalesce(func.max(event_table.c.seq), 0)).where(
            event_table.c.device_id == SERVER_DEVICE_ID
        )
    ).scalar_one()
    return highest + 1


def author(
    conn: Connection,
    *,
    event_type: EventType,
    entity_id: int,
    payload: dict,
    incident_id: int,
    responder_id: int = COMMANDER_RESPONDER_ID,
    team_id: int = COMMANDER_TEAM_ID,
    agency_id: int = COMMANDER_AGENCY_ID,
):
    """Author and append one server event, returning ``(event, AppendResult)``."""
    canonical = CanonicalEvent(
        device_id=SERVER_DEVICE_ID,
        seq=next_server_seq(conn),
        type=event_type,
        entity_type=entity_type_for(event_type),
        entity_id=entity_id,
        payload=payload,
        t_dev=datetime.now(timezone.utc),
        responder_id=responder_id,
        team_id=team_id,
        agency_id=agency_id,
        incident_id=incident_id,
        schema_version=CURRENT_SCHEMA_VERSION,
    )
    result = append(conn, canonical, received_via=ReceivedVia.INTERNET)
    return canonical, result
