"""Request-scoped dependencies.

The engine is built once from configuration and reused. **No authentication is
applied at M4** — endpoints 1, 2 and 6 and all auth enforcement are M5
(docs/12 §3.2.1, transitional state).
"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Connection

from rescuenet.services.errors import unavailable


def db(request: Request) -> Iterator[Connection]:
    engine = getattr(request.app.state, "engine", None)
    if engine is None:
        raise unavailable("database is not configured")
    try:
        with engine.begin() as conn:
            yield conn
    except Exception as exc:  # pragma: no cover - surfaced as 503
        from rescuenet.services.errors import ApiError

        if isinstance(exc, ApiError):
            raise
        raise
