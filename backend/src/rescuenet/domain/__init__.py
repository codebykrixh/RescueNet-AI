"""RescueNet backend — domain. Canonical event model (docs/08, milestone M2).

Pure: no HTTP, no SQL, no broker, no wire format (docs/06 §3 rule 1, AD-03).
"""

from rescuenet.domain.enums import (
    CellStatus,
    DisasterType,
    EntityType,
    EventType,
    Priority,
    ReceivedVia,
    SurvivorStatus,
    TeamStatus,
    Triage,
    entity_type_for,
    priority_for,
)
from rescuenet.domain.event import (
    PAYLOAD_MODEL,
    CanonicalEvent,
    EventIdentity,
    parse_event,
)
from rescuenet.domain.grid import (
    Grid,
    GridError,
    column_index,
    column_letters,
    is_representable_cell_index,
)
from rescuenet.domain.limits import (
    MAX_CELL_INDEX,
    MAX_CELLS,
    RESERVED_CELL_INDEX,
    SERVER_DEVICE_ID,
)
from rescuenet.domain.validation import (
    CodeClass,
    EventValidationError,
    RejectionCode,
    code_class,
    is_retryable,
    may_permanently_reject,
)

__all__ = [
    "CanonicalEvent", "EventIdentity", "parse_event", "PAYLOAD_MODEL",
    "EventType", "EntityType", "Priority", "ReceivedVia", "CellStatus",
    "SurvivorStatus", "Triage", "TeamStatus", "DisasterType",
    "priority_for", "entity_type_for",
    "Grid", "GridError", "is_representable_cell_index",
    "column_letters", "column_index",
    "MAX_CELLS", "MAX_CELL_INDEX", "RESERVED_CELL_INDEX", "SERVER_DEVICE_ID",
    "RejectionCode", "CodeClass", "EventValidationError",
    "code_class", "is_retryable", "may_permanently_reject",
]
