"""Alembic environment (milestone M3).

The URL comes from ``RESCUENET_DATABASE_URL`` — the same single variable the
application reads, resolved per environment (README). Migrations run as the
database owner, not as the restricted application role, because they create
schema and grants.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rescuenet.store.tables import metadata  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.environ.get("RESCUENET_DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "RESCUENET_DATABASE_URL is not set. Resolve it per environment:\n"
        '  export RESCUENET_DATABASE_URL="$(grep \'^DATABASE_URL_HOST=\' '
        '../deploy/.env | cut -d= -f2-)"'
    )
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = metadata


def run_migrations_offline() -> None:
    context.configure(url=DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
