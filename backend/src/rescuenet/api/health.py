"""Liveness endpoint (docs/09 §1.2 endpoint 14, docs/12 M1).

Contract: ``GET /health`` returns ``{status, db, broker}``, unauthenticated,
exposing no operational data.
"""

from __future__ import annotations

from enum import Enum

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class ComponentStatus(str, Enum):
    """State of a backing service.

    ``UNCHECKED`` is the honest value while the component that would perform the
    check does not exist yet: the event store arrives at M3 and the MQTT
    publisher at M10 (docs/12). It is deliberately not ``OK`` — reporting a
    component healthy without checking it would be a fabricated result.
    """

    OK = "ok"
    UNCHECKED = "unchecked"
    ERROR = "error"


class HealthResponse(BaseModel):
    """Exactly the three fields docs/09 specifies. No operational data."""

    status: str
    db: ComponentStatus
    broker: ComponentStatus


@router.get("/health", response_model=HealthResponse, summary="Liveness")
def health() -> HealthResponse:
    """Report that the application is serving.

    ``status`` describes the application process only. ``db`` and ``broker``
    remain ``unchecked`` until M3 and M10 supply components able to check them.
    """
    return HealthResponse(
        status="ok",
        db=ComponentStatus.UNCHECKED,
        broker=ComponentStatus.UNCHECKED,
    )
