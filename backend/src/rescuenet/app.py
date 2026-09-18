"""FastAPI application bootstrap (docs/07 T-04/T-05, docs/12 M1).

Modular monolith, single deployable. This module wires configuration, logging
and routing, and nothing else — domain, store, projections, auth and mqtt are
delivered by later milestones.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rescuenet.api import errors as api_errors
from rescuenet.api.health import router as health_router
from rescuenet.api.m5 import router as m5_router
from rescuenet.api.v1 import router as v1_router
from rescuenet.config.logging import configure_logging
from rescuenet.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

API_TITLE = "RescueNet AI"
API_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown.

    No database or broker connection is opened here: those components arrive at
    M3 and M10 respectively (docs/12).
    """
    settings: Settings = app.state.settings
    engine = None
    if settings.database_url is not None:
        from rescuenet.store import make_engine

        engine = make_engine(settings.database_url.get_secret_value())
    app.state.engine = engine
    logger.info(
        "backend starting",
        extra={"app_env": settings.app_env.value, "milestone": "M4",
               "database_configured": engine is not None},
    )
    yield
    if engine is not None:
        engine.dispose()
    logger.info("backend stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory.

    Accepting settings makes the app testable without touching the environment.
    """
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=(
            "Multi-agency search-and-rescue coordination. "
            "REST is authoritative for all durable writes and reads."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = None

    api_errors.install(app)

    # M1 liveness plus the 11 M4 operational endpoints. Endpoints 1, 2 and 6
    # (enrol, session, join-code) are M5 and deliberately absent (docs/12 §3.2).
    app.include_router(health_router)
    app.include_router(v1_router)
    app.include_router(m5_router)

    return app


app = create_app()
