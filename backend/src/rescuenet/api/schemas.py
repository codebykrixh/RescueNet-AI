"""Request/response models for the M4 endpoints (docs/09 Part 1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from rescuenet.domain.enums import DisasterType
from rescuenet.domain.limits import (
    MAX_AGENCY_ID, MAX_CELLS, MAX_TEAM_ID,
)


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IncidentCreate(_Body):
    name: str = Field(min_length=1, max_length=200)
    disaster_type: DisasterType
    origin_lat: float = Field(ge=-90, le=90)
    origin_lon: float = Field(ge=-180, le=180)
    started_at: datetime
    notes: str | None = Field(default=None, max_length=1000)


class IncidentCreated(BaseModel):
    incident_id: int
    server_seq: int


class GridCreate(_Body):
    origin_lat: float = Field(ge=-90, le=90)
    origin_lon: float = Field(ge=-180, le=180)
    cell_size_m: float = Field(gt=0)
    rows: int = Field(ge=1, le=MAX_CELLS)
    cols: int = Field(ge=1, le=MAX_CELLS)
    bearing_deg: float = Field(default=0.0, ge=0, lt=360)


class GridCreated(BaseModel):
    incident_id: int
    cell_count: int
    server_seq: int


class TeamCreate(_Body):
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    callsign: str = Field(min_length=1, max_length=64)
    agency_id: int = Field(ge=0, le=MAX_AGENCY_ID)
    agency_type: str = Field(min_length=1, max_length=64)
    incident_id: int = Field(ge=0)


class TeamCreated(BaseModel):
    team_id: int
    server_seq: int


class EventBatch(_Body):
    batch_id: str | None = None
    origin_device_id: int | None = None
    mac: str | None = None
    events: list[dict[str, Any]] = Field(min_length=1)


class AcceptedEvent(BaseModel):
    device_id: int
    seq: int
    server_seq: int
    was_duplicate: bool


class RejectedEvent(BaseModel):
    device_id: int | None = None
    seq: int | None = None
    code: str
    retryable: bool
    message: str


class IngestResult(BaseModel):
    accepted: list[AcceptedEvent]
    rejected: list[RejectedEvent]
    server_seq_high: int


class DeltaPage(BaseModel):
    events: list[dict[str, Any]]
    next_since: int
    has_more: bool
    current_server_seq: int


class AssignmentCreate(_Body):
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    cell_ids: list[int] = Field(min_length=1)
    incident_id: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=500)


class HeldCell(BaseModel):
    cell_index: int
    team_id: int | None


class AssignmentCreated(BaseModel):
    assignment_id: int
    server_seq: int
    already_held: list[HeldCell]


class AssignmentRevoked(BaseModel):
    server_seq: int


class SyncDiagnostics(BaseModel):
    current_server_seq: int
    events_total: int
    events_by_transport: dict[str, int]
    projection_lag: int
    mqtt_connected: bool
    last_publish_server_seq: int | None
