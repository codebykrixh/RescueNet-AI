"""Per-type payloads (docs/08 Part 2).

Each model carries exactly the required and optional fields docs/08 defines for
its type — no more. ``extra="forbid"`` makes an undeclared field a validation
error rather than silently accepted data.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from rescuenet.domain.enums import (
    CellStatus,
    DisasterType,
    SurvivorStatus,
    TeamStatus,
    Triage,
)
from rescuenet.domain.limits import (
    MAX_AGENCY_ID,
    MAX_CELL_INDEX,
    MAX_CELLS,
    MAX_DEVICE_ID,
    MAX_ITEM_ID,
    MAX_PERSON_COUNT,
    MAX_QTY_DELTA,
    MAX_REL_COORD,
    MAX_RESPONDER_ID,
    MAX_TEAM_ID,
    MIN_QTY_DELTA,
    MIN_REL_COORD,
)


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# --- Server-authored (docs/08 §2.1) ---------------------------------------

class IncidentDeclaredPayload(_Payload):
    name: str = Field(min_length=1)
    disaster_type: DisasterType
    origin_lat: float = Field(ge=-90.0, le=90.0)
    origin_lon: float = Field(ge=-180.0, le=180.0)
    started_at: str
    notes: str | None = None


class GridGeneratedPayload(_Payload):
    origin_lat: float = Field(ge=-90.0, le=90.0)
    origin_lon: float = Field(ge=-180.0, le=180.0)
    cell_size_m: float = Field(gt=0)
    rows: int = Field(ge=1, le=MAX_CELLS)
    cols: int = Field(ge=1, le=MAX_CELLS)
    bearing_deg: float = Field(ge=0.0, lt=360.0)

    def model_post_init(self, _context: object) -> None:
        """docs/09 §10.5 — the wire field bounds the grid (audit F-01)."""
        if self.rows * self.cols > MAX_CELLS:
            raise ValueError(
                f"grid of {self.rows}x{self.cols}={self.rows * self.cols} cells "
                f"exceeds MAX_CELLS={MAX_CELLS} (docs/09 §10.5)"
            )


class TeamRegisteredPayload(_Payload):
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    callsign: str = Field(min_length=1)
    agency_id: int = Field(ge=0, le=MAX_AGENCY_ID)
    agency_type: str = Field(min_length=1)


class DeviceEnrolledPayload(_Payload):
    device_id: int = Field(ge=0, le=MAX_DEVICE_ID)
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    responder_id: int = Field(ge=0, le=MAX_RESPONDER_ID)
    label: str | None = None


class AssignmentIssuedPayload(_Payload):
    assignment_id: int = Field(ge=0)
    team_id: int = Field(ge=0, le=MAX_TEAM_ID)
    cell_ids: list[int] = Field(min_length=1)
    note: str | None = None

    def model_post_init(self, _context: object) -> None:
        for cell in self.cell_ids:
            if not 0 <= cell <= MAX_CELL_INDEX:
                raise ValueError(
                    f"cell_ids contains {cell}, outside 0..{MAX_CELL_INDEX} "
                    f"(docs/09 §10.5)"
                )


class AssignmentRevokedPayload(_Payload):
    assignment_id: int = Field(ge=0)
    reason: str | None = None


# --- Device-authored (docs/08 §2.2) ---------------------------------------

class CellStatusReportedPayload(_Payload):
    cell_index: int = Field(ge=0, le=MAX_CELL_INDEX)
    status: CellStatus


class SurvivorReportedPayload(_Payload):
    cell_index: int = Field(ge=0, le=MAX_CELL_INDEX)
    person_count: int = Field(ge=0, le=MAX_PERSON_COUNT)
    survivor_status: SurvivorStatus
    triage: Triage | None = None
    rel_lat: int | None = Field(default=None, ge=MIN_REL_COORD, le=MAX_REL_COORD)
    rel_lon: int | None = Field(default=None, ge=MIN_REL_COORD, le=MAX_REL_COORD)


class ResourceDeltaReportedPayload(_Payload):
    item_id: int = Field(ge=0, le=MAX_ITEM_ID)
    qty_delta: int = Field(ge=MIN_QTY_DELTA, le=MAX_QTY_DELTA)


class PositionReportedPayload(_Payload):
    rel_lat: int = Field(ge=MIN_REL_COORD, le=MAX_REL_COORD)
    rel_lon: int = Field(ge=MIN_REL_COORD, le=MAX_REL_COORD)
    accuracy_m: float | None = Field(default=None, ge=0)
    cell_index: int | None = Field(default=None, ge=0, le=MAX_CELL_INDEX)


class TeamStatusReportedPayload(_Payload):
    team_status: TeamStatus
    note: str | None = None
