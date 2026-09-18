"""M4 — reference tables and the event.incident_id foreign key.

Revision ID: 0002_m4_reference_tables
Revises: 0001_m3_event_store
Create Date: 2026-08-23

Creates the three M4-owned reference tables of docs/08 §11.1 and adds the
`event.incident_id` foreign key that M3 could not add because its target did not
exist (docs/12 §3.1).

Does NOT create `device_credential` or `join_code` — both are M5 (docs/12 §3.2).
Does NOT alter any existing M3 column, index, grant or constraint.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_m4_reference_tables"
down_revision = "0001_m3_event_store"
branch_labels = None
depends_on = None

APP_ROLE = "rescuenet_app"
REFERENCE_TABLES = ("incident", "agency", "resource_item")

#: docs/08 §14.1 — ratified wire code for INCIDENT_DECLARED.
INCIDENT_DECLARED_CODE = 1

BACKFILL_INCIDENTS = """
INSERT INTO incident (incident_id, name, disaster_type, origin_lat,
                      origin_lon, started_at, notes)
SELECT DISTINCT ON (e.incident_id)
       e.incident_id,
       e.payload->>'name',
       e.payload->>'disaster_type',
       (e.payload->>'origin_lat')::double precision,
       (e.payload->>'origin_lon')::double precision,
       (e.payload->>'started_at')::timestamptz,
       e.payload->>'notes'
FROM event e
WHERE e.type = :declared
ORDER BY e.incident_id, e.server_seq
ON CONFLICT (incident_id) DO NOTHING
"""

FIND_ORPHANS = """
SELECT DISTINCT incident_id FROM event e
WHERE NOT EXISTS (SELECT 1 FROM incident i WHERE i.incident_id = e.incident_id)
"""


def upgrade() -> None:
    op.create_table(
        "incident",
        sa.Column("incident_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("disaster_type", sa.String(32), nullable=False),
        sa.Column("origin_lat", sa.Float, nullable=False),
        sa.Column("origin_lon", sa.Float, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
    )
    op.create_table(
        "agency",
        sa.Column("agency_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("agency_type", sa.String(64), nullable=False),
    )
    op.create_table(
        "resource_item",
        sa.Column("item_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
    )

    # docs/08 §11.1: `incident_id | int | FK -> incident`. Deferred from M3
    # because the target table did not exist (docs/12 §3.1). The column itself
    # is unchanged — only the constraint is added.
    #
    # A populated `event` table cannot gain this constraint while rows reference
    # incidents that do not exist. The event log is the source of truth, so any
    # incident it already declared is backfilled from INCIDENT_DECLARED first.
    conn = op.get_bind()
    conn.execute(sa.text(BACKFILL_INCIDENTS), {"declared": INCIDENT_DECLARED_CODE})

    # Anything still unreferenced means the log holds events for an incident it
    # never declared. Refuse rather than invent a row or silently skip the
    # constraint — either would hide real data corruption.
    orphans = conn.execute(sa.text(FIND_ORPHANS)).scalars().all()
    if orphans:
        raise RuntimeError(
            "cannot add fk_event_incident: event rows reference incident_id "
            f"{sorted(orphans)} with no INCIDENT_DECLARED event to backfill "
            "from. Declare those incidents, or remove the orphaned events."
        )

    op.create_foreign_key(
        "fk_event_incident", "event", "incident",
        ["incident_id"], ["incident_id"],
    )

    # Reference tables are written by M4 endpoints, so the restricted role needs
    # DML on them. The `event` grant is NOT touched: it stays INSERT/SELECT only.
    for table in REFERENCE_TABLES:
        op.execute(sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {APP_ROLE}"
        ))
    op.execute(sa.text(
        f"GRANT USAGE, SELECT ON SEQUENCE incident_incident_id_seq TO {APP_ROLE}"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        f"REVOKE ALL ON SEQUENCE incident_incident_id_seq FROM {APP_ROLE}"))
    for table in REFERENCE_TABLES:
        op.execute(sa.text(f"REVOKE ALL ON TABLE {table} FROM {APP_ROLE}"))
    op.drop_constraint("fk_event_incident", "event", type_="foreignkey")
    for table in reversed(REFERENCE_TABLES):
        op.drop_table(table)
