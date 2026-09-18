"""The canonical event (docs/08 Part 1).

One structure for every event; types differ only in ``payload``. The field set
is exactly docs/08 Part 1.1 — no priority (DM-02), no MAC (DM-03), no transport
or database fields. ``extra="forbid"`` makes that enforceable rather than
aspirational.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rescuenet.domain.enums import (
    EntityType,
    EventType,
    Priority,
    ReceivedVia,
    entity_type_for,
    priority_for,
)
from rescuenet.domain.limits import (
    CURRENT_SCHEMA_VERSION,
    MAX_AGENCY_ID,
    MAX_DEVICE_ID,
    MAX_RESPONDER_ID,
    MAX_SEQ,
    MAX_TEAM_ID,
    SERVER_DEVICE_ID,
)
from rescuenet.domain.payloads import (
    AssignmentIssuedPayload,
    AssignmentRevokedPayload,
    CellStatusReportedPayload,
    DeviceEnrolledPayload,
    GridGeneratedPayload,
    IncidentDeclaredPayload,
    PositionReportedPayload,
    ResourceDeltaReportedPayload,
    SurvivorReportedPayload,
    TeamRegisteredPayload,
    TeamStatusReportedPayload,
)
from rescuenet.domain.validation import EventValidationError, RejectionCode

#: docs/08 Part 2 — the payload model each type must carry.
PAYLOAD_MODEL: dict[EventType, type] = {
    EventType.INCIDENT_DECLARED: IncidentDeclaredPayload,
    EventType.GRID_GENERATED: GridGeneratedPayload,
    EventType.TEAM_REGISTERED: TeamRegisteredPayload,
    EventType.DEVICE_ENROLLED: DeviceEnrolledPayload,
    EventType.ASSIGNMENT_ISSUED: AssignmentIssuedPayload,
    EventType.ASSIGNMENT_REVOKED: AssignmentRevokedPayload,
    EventType.CELL_STATUS_REPORTED: CellStatusReportedPayload,
    EventType.SURVIVOR_REPORTED: SurvivorReportedPayload,
    EventType.RESOURCE_DELTA_REPORTED: ResourceDeltaReportedPayload,
    EventType.POSITION_REPORTED: PositionReportedPayload,
    EventType.TEAM_STATUS_REPORTED: TeamStatusReportedPayload,
}

AnyPayload = Union[tuple(dict.fromkeys(PAYLOAD_MODEL.values()))]  # type: ignore[misc]

#: Which payload field names ``entity_id`` where a type has a natural subject.
#: Demonstrated by every example in docs/08 Part 16.
_ENTITY_ID_SOURCE: dict[EventType, str] = {
    EventType.GRID_GENERATED: "__incident__",
    EventType.INCIDENT_DECLARED: "__incident__",
    EventType.TEAM_REGISTERED: "team_id",
    EventType.DEVICE_ENROLLED: "device_id",
    EventType.ASSIGNMENT_ISSUED: "assignment_id",
    EventType.ASSIGNMENT_REVOKED: "assignment_id",
    EventType.CELL_STATUS_REPORTED: "cell_index",
    EventType.RESOURCE_DELTA_REPORTED: "item_id",
    EventType.POSITION_REPORTED: "__team__",
    EventType.TEAM_STATUS_REPORTED: "__team__",
    # SURVIVOR_REPORTED: entity_id is 0 — the event IS the entity (docs/08 §16.4).
}


class EventIdentity(BaseModel):
    """``(device_id, seq)`` — D-05, DM-06.

    Assignable entirely offline with no coordination, and 4 bytes on the wire
    where a UUID would cost 16 (docs/04 §3.1 finding 4).
    """

    model_config = ConfigDict(frozen=True)

    device_id: int = Field(ge=0, le=MAX_DEVICE_ID)
    seq: int = Field(ge=0, le=MAX_SEQ)

    @property
    def is_server_authored(self) -> bool:
        """docs/08 DM-36 — ``device_id`` 0 is reserved for the server."""
        return self.device_id == SERVER_DEVICE_ID

    def __str__(self) -> str:
        return f"({self.device_id},{self.seq})"


class CanonicalEvent(BaseModel):
    """An immutable operational fact (docs/08 Part 1.1).

    Device-assigned fields are always present. ``server_seq``, ``t_srv`` and
    ``received_via`` are assigned at ingestion and are therefore optional until
    then (docs/08 §16.7).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- identity (device-assigned) ---
    device_id: int = Field(ge=0, le=MAX_DEVICE_ID)
    seq: int = Field(ge=0, le=MAX_SEQ)

    # --- classification (device-assigned) ---
    type: EventType
    entity_type: EntityType
    entity_id: int = Field(ge=0)
    payload: dict[str, Any]

    # --- attribution (device-assigned) ---
    t_dev: datetime
    responder_id: int = Field(ge=0, le=MAX_RESPONDER_ID)
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    agency_id: int = Field(ge=0, le=MAX_AGENCY_ID)
    incident_id: int = Field(ge=0)
    schema_version: int = Field(ge=1)

    # --- server-assigned ---
    server_seq: int | None = Field(default=None, ge=0)
    t_srv: datetime | None = None
    received_via: ReceivedVia | None = None

    # -- derived, never stored --------------------------------------------
    @property
    def identity(self) -> EventIdentity:
        return EventIdentity(device_id=self.device_id, seq=self.seq)

    @property
    def priority(self) -> Priority:
        """Derived from type — the single source of truth (DM-02)."""
        return priority_for(self.type)

    @property
    def is_committed(self) -> bool:
        return self.server_seq is not None

    # -- structural validation --------------------------------------------
    @model_validator(mode="after")
    def _entity_type_matches_event_type(self) -> CanonicalEvent:
        """docs/09 §10.4 — ``entity_type`` is implied by ``type``."""
        expected = entity_type_for(self.type)
        if self.entity_type is not expected:
            raise ValueError(
                f"{self.type.value} implies entity_type {expected.value}, "
                f"got {self.entity_type.value}"
            )
        return self

    @model_validator(mode="after")
    def _payload_matches_type(self) -> CanonicalEvent:
        """docs/08 Part 2 — the payload carries exactly its type's fields."""
        model = PAYLOAD_MODEL[self.type]
        try:
            model(**self.payload)
        except Exception as exc:
            raise ValueError(f"payload invalid for {self.type.value}: {exc}") from exc
        return self

    @model_validator(mode="after")
    def _entity_id_agrees_with_payload(self) -> CanonicalEvent:
        """``entity_id`` names the subject the payload describes.

        Every example in docs/08 Part 16 shows this agreement; enforcing it
        prevents an event whose subject contradicts its own content.
        """
        source = _ENTITY_ID_SOURCE.get(self.type)
        if source is None:                       # SURVIVOR_REPORTED
            if self.entity_id != 0:
                raise ValueError(
                    "SURVIVOR_REPORTED carries entity_id 0 — the event is the "
                    "entity, identified by (device_id, seq) (docs/08 §16.4)"
                )
            return self
        expected = {
            "__incident__": self.incident_id,
            "__team__": self.team_id,
        }.get(source, self.payload.get(source))
        if expected is not None and self.entity_id != expected:
            raise ValueError(
                f"entity_id {self.entity_id} disagrees with {source}={expected}"
            )
        return self

    def typed_payload(self):
        """The payload as its type-specific model."""
        return PAYLOAD_MODEL[self.type](**self.payload)


def parse_event(raw: dict[str, Any]) -> CanonicalEvent:
    """Parse an event, mapping failures to docs/09 §2.6 rejection codes.

    Only codes decidable from the event alone are produced here. Codes needing
    server context are applied at ingestion (M3/M4).
    """
    if not isinstance(raw, dict):
        raise EventValidationError(
            RejectionCode.INVALID_PAYLOAD, "event must be an object"
        )

    raw_type = raw.get("type")
    if raw_type is not None and raw_type not in {t.value for t in EventType}:
        raise EventValidationError(
            RejectionCode.UNKNOWN_TYPE, f"unknown event type {raw_type!r}"
        )

    version = raw.get("schema_version")
    if isinstance(version, int) and version > CURRENT_SCHEMA_VERSION:
        raise EventValidationError(
            RejectionCode.UNSUPPORTED_SCHEMA,
            f"schema_version {version} exceeds supported {CURRENT_SCHEMA_VERSION}",
        )

    try:
        return CanonicalEvent(**raw)
    except Exception as exc:
        raise EventValidationError(RejectionCode.INVALID_PAYLOAD, str(exc)) from exc
