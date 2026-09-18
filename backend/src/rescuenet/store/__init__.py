"""RescueNet backend — store. PostgreSQL event store (docs/08 Part 11, milestone M3).

Persistence only. The canonical event model lives in ``rescuenet.domain`` and is
not redefined here.
"""

from rescuenet.store.engine import APP_ROLE, connection, current_role, make_engine
from rescuenet.store.events import (
    AppendResult,
    append,
    append_many,
    count,
    max_server_seq,
    read_entity_history,
    read_since,
)
from rescuenet.store.tables import READ_MODELS, event, metadata

__all__ = [
    "make_engine", "connection", "current_role", "APP_ROLE",
    "append", "append_many", "read_since", "read_entity_history",
    "max_server_seq", "count", "AppendResult",
    "metadata", "event", "READ_MODELS",
]
