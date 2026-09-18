"""The 11 M4 operational endpoints (docs/09 §1.1, docs/12 §3.2).

Endpoints 1, 2 and 6 are **M5** and deliberately absent. Routes translate HTTP
and delegate to ``rescuenet.services`` — no SQL and no merge logic here.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import HTTPException, APIRouter, Depends, Query, Response, status
from sqlalchemy import Connection

from rescuenet.api import schemas
from rescuenet.api.auth import (
    DeviceOrGateway, DeviceOrSession, Session,
    require_incident_membership, require_scope,
)
from rescuenet.api.deps import db
from rescuenet.services import batch_mac, assignments, incidents, ingestion, queries

router = APIRouter(prefix="/v1")
Db = Annotated[Connection, Depends(db)]


# ── 3 ────────────────────────────────────────────────────────────────────────
@router.post("/incidents", response_model=schemas.IncidentCreated,
             status_code=status.HTTP_201_CREATED, tags=["incident"],
             summary="Declare an incident")
def declare_incident(body: schemas.IncidentCreate, conn: Db, caller: Session):
    return incidents.declare_incident(conn, body.model_dump())


# ── 4 ────────────────────────────────────────────────────────────────────────
@router.post("/incidents/{incident_id}/grid", response_model=schemas.GridCreated,
             status_code=status.HTTP_201_CREATED, tags=["incident"],
             summary="Generate the grid")
def generate_grid(incident_id: int, body: schemas.GridCreate, conn: Db,
                  caller: Session):
    require_incident_membership(caller, incident_id)
    return incidents.generate_grid(conn, incident_id, body.model_dump())


# ── 5 ────────────────────────────────────────────────────────────────────────
@router.post("/teams", response_model=schemas.TeamCreated,
             status_code=status.HTTP_201_CREATED, tags=["team"],
             summary="Register a team")
def register_team(body: schemas.TeamCreate, conn: Db, caller: Session):
    data = body.model_dump()
    return incidents.register_team(conn, data, data["incident_id"])


# ── 7 ────────────────────────────────────────────────────────────────────────
@router.post("/events", response_model=schemas.IngestResult, tags=["events"],
             summary="Batch event upload")
def upload_events(batch: schemas.EventBatch, conn: Db, caller: DeviceOrGateway):
    """Partial acceptance: 200 even when some events are rejected (AP-04).

    A ``GATEWAY`` batch is MAC-verified first (TR-10, AP-16, DM-49). A failure is
    **request-level**: 401 with **zero events persisted** — never a per-event
    rejection, because the batch was never evaluated (AP-22). This closes DM-51.
    """
    data = batch.model_dump()
    try:
        batch_mac.verify_gateway_batch(conn, data, caller)
    except batch_mac.BatchMacError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return ingestion.ingest_batch(conn, data, caller)


# ── 8 ────────────────────────────────────────────────────────────────────────
@router.get("/events", response_model=schemas.DeltaPage, tags=["events"],
            summary="Delta sync and audit history")
def read_events(
    conn: Db,
    since: int = Query(0, ge=0, description="Cursor — exclusive lower bound on server_seq"),
    limit: int = Query(queries.DEFAULT_PAGE, ge=1, le=queries.MAX_PAGE),
    entity_type: str | None = None,
    entity_id: int | None = None,
    team_id: int | None = None,
    type: str | None = None,
    caller: DeviceOrSession = None,
):
    return queries.delta(conn, since=since, limit=limit, entity_type=entity_type,
                         entity_id=entity_id, team_id=team_id, event_type=type)


# ── 9 ────────────────────────────────────────────────────────────────────────
@router.get("/incidents/{incident_id}/snapshot", tags=["incident"],
            summary="Initial load")
def snapshot(incident_id: int, conn: Db, caller: DeviceOrSession,
             scope: str = Query("command", pattern="^(field|command)$")) -> dict[str, Any]:
    # docs/09 §1.2 endpoint 9: membership, and scope constrained by role.
    require_incident_membership(caller, incident_id)
    require_scope(caller, scope)
    return queries.snapshot(conn, incident_id, scope)


# ── 10 ───────────────────────────────────────────────────────────────────────
@router.post("/assignments", response_model=schemas.AssignmentCreated,
             status_code=status.HTTP_201_CREATED, tags=["assignment"],
             summary="Issue an assignment")
def issue_assignment(body: schemas.AssignmentCreate, conn: Db, caller: Session):
    data = body.model_dump()
    require_incident_membership(caller, data["incident_id"])
    return assignments.issue(conn, data, data["incident_id"])


# ── 11 ───────────────────────────────────────────────────────────────────────
@router.delete("/assignments/{assignment_id}",
               response_model=schemas.AssignmentRevoked, tags=["assignment"],
               summary="Revoke an assignment")
def revoke_assignment(assignment_id: int, conn: Db, caller: Session,
                      reason: str | None = None):
    return assignments.revoke(conn, assignment_id, reason)


# ── 12 ───────────────────────────────────────────────────────────────────────
@router.get("/incidents/{incident_id}/export", tags=["incident"],
            summary="GeoJSON / CSV export")
def export(incident_id: int, conn: Db, caller: Session,
           format: str = Query("geojson", pattern="^(geojson|csv)$")) -> Response:
    require_incident_membership(caller, incident_id)
    payload, media_type = queries.export(conn, incident_id, format)
    return Response(content=payload, media_type=media_type)


# ── 13 ───────────────────────────────────────────────────────────────────────
@router.get("/diag/sync", response_model=schemas.SyncDiagnostics, tags=["ops"],
            summary="Sync diagnostics")
def sync_diagnostics(conn: Db, caller: Session):
    return queries.diagnostics(conn)
