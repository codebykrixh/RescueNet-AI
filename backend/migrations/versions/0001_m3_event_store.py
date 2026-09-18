"""M3 — append-only event store, derived read models, restricted app role.

Revision ID: 0001_m3_event_store
Revises:
Create Date: 2026-08-23

Implements docs/08 §11.1 (event table) and §11.2 (read models), plus the
append-only grant of DM-29.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_m3_event_store"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "rescuenet_app"

#: Disposable, rebuildable from `event` alone (DM-30). The app needs full DML
#: on these, and INSERT/SELECT only on `event`.
READ_MODEL_TABLES = (
    "cell_state", "duplicate_search", "assignment_state", "team_state",
    "team_position", "resource_stock", "survivor_report", "coverage_metrics",
    "projection_state",
)


def upgrade() -> None:
    # ── source of truth (docs/08 §11.1) ─────────────────────────────────────
    op.create_table(
        "event",
        sa.Column("device_id", sa.Integer, nullable=False),
        sa.Column("seq", sa.BigInteger, nullable=False),
        sa.Column("server_seq", sa.BigInteger, sa.Identity(always=True), nullable=False),
        sa.Column("incident_id", sa.Integer, nullable=False),
        sa.Column("type", sa.SmallInteger, nullable=False),
        sa.Column("entity_type", sa.SmallInteger, nullable=False),
        sa.Column("entity_id", sa.BigInteger, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("t_dev", sa.DateTime(timezone=True), nullable=False),
        sa.Column("t_srv", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("schema_version", sa.SmallInteger, nullable=False),
        sa.Column("responder_id", sa.Integer, nullable=False),
        sa.Column("team_id", sa.Integer, nullable=False),
        sa.Column("agency_id", sa.Integer, nullable=False),
        sa.Column("received_via", sa.SmallInteger, nullable=True),
        # (device_id, seq) is the event identity — D-05, DM-06. Making it the
        # primary key is what makes ingestion idempotent by construction.
        sa.PrimaryKeyConstraint("device_id", "seq", name="pk_event"),
        sa.UniqueConstraint("server_seq", name="uq_event_server_seq"),
    )
    op.create_index("ix_event_server_seq", "event", ["server_seq"])
    op.create_index("ix_event_incident_server_seq", "event", ["incident_id", "server_seq"])
    op.create_index("ix_event_entity_server_seq", "event",
                    ["entity_type", "entity_id", "server_seq"])
    op.create_index("ix_event_team_server_seq", "event", ["team_id", "server_seq"])
    op.create_index("ix_event_type_incident", "event", ["type", "incident_id"])

    # ── derived read models (docs/08 §11.2) ─────────────────────────────────
    op.create_table(
        "cell_state",
        sa.Column("incident_id", sa.Integer, primary_key=True),
        sa.Column("cell_index", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("team_id", sa.Integer, nullable=True),
        sa.Column("last_server_seq", sa.BigInteger, nullable=True),
    )
    op.create_table(
        "duplicate_search",
        sa.Column("incident_id", sa.Integer, primary_key=True),
        sa.Column("cell_index", sa.Integer, primary_key=True),
        sa.Column("team_count", sa.Integer, nullable=False),
        sa.Column("team_ids", JSONB, nullable=False),
    )
    op.create_table(
        "assignment_state",
        sa.Column("incident_id", sa.Integer, primary_key=True),
        sa.Column("cell_index", sa.Integer, primary_key=True),
        sa.Column("team_id", sa.Integer, nullable=True),
        sa.Column("assignment_id", sa.BigInteger, nullable=True),
        sa.Column("last_server_seq", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "team_state",
        sa.Column("team_id", sa.Integer, primary_key=True),
        sa.Column("callsign", sa.String(64), nullable=True),
        sa.Column("agency_id", sa.Integer, nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("last_server_seq", sa.BigInteger, nullable=True),
    )
    op.create_table(
        "team_position",
        sa.Column("team_id", sa.Integer, primary_key=True),
        sa.Column("rel_lat", sa.Integer, nullable=False),
        sa.Column("rel_lon", sa.Integer, nullable=False),
        sa.Column("t_srv", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_server_seq", sa.BigInteger, nullable=False),
    )
    op.create_table(
        "resource_stock",
        sa.Column("team_id", sa.Integer, primary_key=True),
        sa.Column("item_id", sa.Integer, primary_key=True),
        sa.Column("qty", sa.Integer, nullable=False),
    )
    op.create_table(
        "survivor_report",
        sa.Column("device_id", sa.Integer, primary_key=True),
        sa.Column("seq", sa.BigInteger, primary_key=True),
        sa.Column("incident_id", sa.Integer, nullable=False),
        sa.Column("cell_index", sa.Integer, nullable=False),
        sa.Column("person_count", sa.Integer, nullable=False),
        sa.Column("survivor_status", sa.String(32), nullable=False),
        sa.Column("triage", sa.String(16), nullable=True),
        sa.Column("team_id", sa.Integer, nullable=False),
        sa.Column("agency_id", sa.Integer, nullable=False),
        sa.Column("unresolved_cell", sa.Boolean, nullable=False,
                  server_default=sa.text("false")),
        sa.Column("server_seq", sa.BigInteger, nullable=True),
    )
    op.create_table(
        "coverage_metrics",
        sa.Column("incident_id", sa.Integer, primary_key=True),
        sa.Column("total", sa.Integer, nullable=False),
        sa.Column("searched", sa.Integer, nullable=False),
        sa.Column("in_progress", sa.Integer, nullable=False),
        sa.Column("needs_research", sa.Integer, nullable=False),
        sa.Column("assigned", sa.Integer, nullable=False),
        sa.Column("unsearched", sa.Integer, nullable=False),
    )
    op.create_table(
        "projection_state",
        sa.Column("id", sa.SmallInteger, primary_key=True),
        sa.Column("last_projected_server_seq", sa.BigInteger, nullable=False,
                  server_default="0"),
    )

    # ── append-only enforcement (DM-29) ─────────────────────────────────────
    # A table owner always bypasses its own grants, so revoking from the owner
    # would achieve nothing. Instead a dedicated NOLOGIN role holds exactly the
    # privileges the application may use, and the application assumes it with
    # SET ROLE on every connection. No new credentials are introduced.
    op.execute(sa.text(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN;
            END IF;
        END $$;
    """))
    op.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))
    # THE append-only guarantee: INSERT and SELECT, never UPDATE, never DELETE.
    op.execute(sa.text(f"GRANT SELECT, INSERT ON TABLE event TO {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE, TRUNCATE ON TABLE event FROM {APP_ROLE}"))
    # Read models are disposable, so they get full DML.
    for table in READ_MODEL_TABLES:
        op.execute(sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {APP_ROLE}"
        ))
    # Let the connecting owner assume the restricted role.
    op.execute(sa.text(f"GRANT {APP_ROLE} TO CURRENT_USER"))


def downgrade() -> None:
    """Reverse the migration.

    Dropping `event` destroys the source of truth, so downgrade is intended for
    development only — never as a production recovery path. The append-only
    guarantee is preserved while the table exists; it is the drop itself, an
    owner-level DDL operation, that removes it.
    """
    for table in READ_MODEL_TABLES:
        op.execute(sa.text(f"REVOKE ALL ON TABLE {table} FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE ALL ON TABLE event FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE}"))

    for table in reversed(READ_MODEL_TABLES):
        op.drop_table(table)
    op.drop_index("ix_event_type_incident", table_name="event")
    op.drop_index("ix_event_team_server_seq", table_name="event")
    op.drop_index("ix_event_entity_server_seq", table_name="event")
    op.drop_index("ix_event_incident_server_seq", table_name="event")
    op.drop_index("ix_event_server_seq", table_name="event")
    op.drop_table("event")
    op.execute(sa.text(f"DROP ROLE IF EXISTS {APP_ROLE}"))
