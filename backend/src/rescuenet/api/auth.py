"""Authentication and authorization dependencies (docs/09 §1.1 and Part 8, M5).

`GET /health` is the only unauthenticated endpoint. Every other endpoint carries
the Auth requirement documented in `09` §1.1, expressed here as a FastAPI
dependency so the rule sits beside the route it guards.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Connection

from rescuenet.api.deps import db
from rescuenet.services import errors
from rescuenet.services.identity import COMMANDER, DEVICE_ROLES, FIELD, GATEWAY, Principal
from rescuenet.services.identity import resolve_token

Db = Annotated[Connection, Depends(db)]


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise errors.ApiError(401, "UNAUTHENTICATED",
                              "missing or malformed Authorization header")
    return token.strip()


def principal(request: Request, conn: Db) -> Principal:
    """Any valid, unrevoked, unexpired credential."""
    return resolve_token(conn, _bearer(request))


AnyPrincipal = Annotated[Principal, Depends(principal)]


def _require(p: Principal, allowed: frozenset[str]) -> Principal:
    if p.role not in allowed:
        raise errors.ApiError(
            403, "FORBIDDEN",
            f"role {p.role} may not use this endpoint",
            details={"required": sorted(allowed)},
        )
    return p


def require_session(p: AnyPrincipal) -> Principal:
    """`09` §1.1 Auth = `Session` — a COMMANDER session token."""
    return _require(p, frozenset({COMMANDER}))


def require_device_or_session(p: AnyPrincipal) -> Principal:
    """`09` §1.1 Auth = `Device or Session`."""
    return _require(p, frozenset({FIELD, GATEWAY, COMMANDER}))


def require_device_or_gateway(p: AnyPrincipal) -> Principal:
    """`09` §1.1 Auth = `Device or Gateway`."""
    return _require(p, DEVICE_ROLES)


Session = Annotated[Principal, Depends(require_session)]
DeviceOrSession = Annotated[Principal, Depends(require_device_or_session)]
DeviceOrGateway = Annotated[Principal, Depends(require_device_or_gateway)]


def require_incident_membership(p: Principal, incident_id: int) -> None:
    """`09` §1.2 endpoint 9 — "caller must belong to the incident".

    A commander's scope is on the credential (DM-50); a device's comes from its
    `DEVICE_ENROLLED` event.
    """
    if p.incident_id is None:
        raise errors.ApiError(403, "NO_INCIDENT_SCOPE",
                              "credential is not scoped to any incident")
    if p.incident_id != incident_id:
        raise errors.ApiError(
            403, "WRONG_INCIDENT",
            "credential is not scoped to this incident",
            details={"incident_id": incident_id},
        )


def require_scope(p: Principal, scope: str) -> None:
    """`09` §1.2 endpoint 9 — "`scope` is constrained by role"."""
    if scope == "command" and not p.is_commander:
        raise errors.ApiError(
            403, "FORBIDDEN",
            "scope=command requires a COMMANDER session",
            details={"role": p.role},
        )
