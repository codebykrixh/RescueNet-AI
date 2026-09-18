"""Database engine and session handling (docs/07 T-06/T-08).

The application always operates under the restricted ``rescuenet_app`` role, so
the append-only guarantee (DM-29) is enforced by the database on every
connection rather than by remembering to be careful.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, create_engine, event as sa_event, text
from sqlalchemy.engine import Engine

#: The restricted role created by the M3 migration. INSERT/SELECT on `event`,
#: full DML on the disposable read models.
APP_ROLE = "rescuenet_app"


def make_engine(database_url: str, *, assume_role: bool = True) -> Engine:
    """Build an engine that switches to the restricted role on every connection.

    ``assume_role=False`` is for migrations and test setup, which legitimately
    need owner rights to create schema and to prove the restriction works.
    """
    engine = create_engine(
        database_url.replace("postgresql+psycopg://", "postgresql+psycopg://"),
        pool_pre_ping=True,
        future=True,
    )

    if assume_role:

        @sa_event.listens_for(engine, "connect")
        def _assume_restricted_role(dbapi_connection, _record) -> None:
            with dbapi_connection.cursor() as cur:
                cur.execute(f"SET ROLE {APP_ROLE}")

    return engine


@contextmanager
def connection(engine: Engine) -> Iterator[Connection]:
    """A transactional connection."""
    with engine.begin() as conn:
        yield conn


def current_role(conn: Connection) -> str:
    return conn.execute(text("select current_user")).scalar_one()
