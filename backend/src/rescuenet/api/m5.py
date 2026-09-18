"""The three M5-owned endpoints: 1, 2 and 6 (docs/12 §3.2)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection

from rescuenet.api.auth import Session
from rescuenet.api.deps import db
from rescuenet.domain.limits import MAX_TEAM_ID
from rescuenet.services import identity

router = APIRouter(prefix="/v1", tags=["auth"])
Db = Annotated[Connection, Depends(db)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EnrolRequest(_Body):
    join_code: str = Field(min_length=1, max_length=16)
    device_label: str | None = Field(default=None, max_length=64)
    mode: str = Field(default="FIELD", pattern="^(FIELD|GATEWAY)$")


class SessionRequest(_Body):
    incident_id: int = Field(ge=0)
    password: str = Field(min_length=1, max_length=256)


class JoinCodeRequest(_Body):
    incident_id: int = Field(ge=0)
    max_uses: int = Field(default=identity.DEFAULT_JOIN_CODE_MAX_USES, ge=1, le=100)


# ── 1 ────────────────────────────────────────────────────────────────────────
@router.post("/enrol", status_code=status.HTTP_201_CREATED,
             summary="Device joins an incident with a join code")
def enrol(body: EnrolRequest, conn: Db) -> dict:
    """Authenticated by the join code itself — no bearer token (`09` endpoint 1).

    Deliberately **non-idempotent**: two enrolments with one code yield two
    distinct `device_id` values (AP-02, TR-33).
    """
    return identity.enrol(conn, body.join_code, body.mode, body.device_label)


# ── 2 ────────────────────────────────────────────────────────────────────────
@router.post("/auth/session", summary="Commander dashboard login")
def open_session(body: SessionRequest, conn: Db, request: Request) -> dict:
    """Authenticated by the incident password (`09` endpoint 2)."""
    settings = request.app.state.settings
    mqtt = None
    if settings.mqtt_host:
        mqtt = {
            "url": f"ws://{settings.mqtt_host}:{settings.mqtt_port}",
            "username": settings.mqtt_username,
            "password": settings.mqtt_password.get_secret_value()
            if settings.mqtt_password else None,
            "topic": f"rescuenet/v1/incident/{body.incident_id}/notify",
        }
    return identity.open_session(conn, body.incident_id, body.password, mqtt)


# ── 6 ────────────────────────────────────────────────────────────────────────
@router.post("/teams/{team_id}/join-code", status_code=status.HTTP_201_CREATED,
             summary="Mint a join code for a team")
def mint_join_code(team_id: int, body: JoinCodeRequest, conn: Db,
                   caller: Session) -> dict:
    from rescuenet.api.auth import require_incident_membership

    require_incident_membership(caller, body.incident_id)
    if not 0 <= team_id <= MAX_TEAM_ID:
        from rescuenet.services import errors

        raise errors.unprocessable("INVALID_TEAM", f"team_id outside 0..{MAX_TEAM_ID}")
    return identity.mint_join_code(conn, team_id, body.incident_id, body.max_uses)
