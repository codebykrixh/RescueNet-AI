"""M5 — credential, session and join-code storage.

Revision ID: 0003_m5_credentials
Revises: 0002_m4_reference_tables
Create Date: 2026-08-23

Creates `device_credential` (docs/08 §11.1b, DM-44/DM-50) and `join_code`
(§11.1a, DM-42), and adds `incident.password_hash` (§11.1c, DM-48).

Does NOT touch the event table, its indexes, its append-only grant, or any M3/M4
semantics. Does NOT implement MAC verification — that is M8 (DM-49).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_m5_credentials"
down_revision = "0002_m4_reference_tables"
branch_labels = None
depends_on = None

APP_ROLE = "rescuenet_app"
NEW_TABLES = ("device_credential", "join_code")


def upgrade() -> None:
    # ── device_credential (docs/08 §11.1b) ──────────────────────────────────
    # Surrogate PK with a nullable-unique device_id: a COMMANDER session is not
    # a device and must not consume the 1..4095 space TR-22 reserves (DM-50).
    op.create_table(
        "device_credential",
        sa.Column("credential_id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer, nullable=True, unique=True),
        sa.Column("token_hash", sa.Text, nullable=False, unique=True),
        sa.Column("hmac_secret", sa.LargeBinary, nullable=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("incident_id", sa.Integer, nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('FIELD','GATEWAY','COMMANDER')", name="ck_credential_role"),
        # A device credential must carry a device_id and a secret; a session must not.
        sa.CheckConstraint(
            "(role = 'COMMANDER' AND device_id IS NULL)"
            " OR (role <> 'COMMANDER' AND device_id IS NOT NULL)",
            name="ck_credential_device_id_by_role"),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.incident_id"],
                                name="fk_credential_incident"),
    )
    op.create_index("ix_credential_token_hash", "device_credential", ["token_hash"])
    op.create_index("ix_credential_device_id", "device_credential", ["device_id"])

    # ── join_code (docs/08 §11.1a, DM-42/DM-45) ─────────────────────────────
    op.create_table(
        "join_code",
        sa.Column("code", sa.Text, primary_key=True),
        sa.Column("team_id", sa.Integer, nullable=False),
        sa.Column("incident_id", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer, nullable=False),
        sa.Column("uses", sa.Integer, nullable=False, server_default="0"),
        sa.CheckConstraint("max_uses > 0", name="ck_join_code_max_uses"),
        sa.CheckConstraint("uses >= 0", name="ck_join_code_uses"),
        sa.ForeignKeyConstraint(["incident_id"], ["incident.incident_id"],
                                name="fk_join_code_incident"),
    )

    # ── incident.password_hash (docs/08 §11.1c, DM-48) ──────────────────────
    # Format: scrypt$n=16384,r=8,p=1$<salt_b64>$<hash_b64>. Nullable so incidents
    # declared before M5 remain valid; a NULL hash simply cannot authenticate.
    op.add_column("incident", sa.Column("password_hash", sa.Text, nullable=True))

    # Grants for the restricted role. The `event` grant is untouched: still
    # INSERT/SELECT only (DM-29).
    for table in NEW_TABLES:
        op.execute(sa.text(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table} TO {APP_ROLE}"))
    op.execute(sa.text(
        "GRANT USAGE, SELECT ON SEQUENCE device_credential_credential_id_seq "
        f"TO {APP_ROLE}"))


def downgrade() -> None:
    op.execute(sa.text(
        "REVOKE ALL ON SEQUENCE device_credential_credential_id_seq "
        f"FROM {APP_ROLE}"))
    for table in NEW_TABLES:
        op.execute(sa.text(f"REVOKE ALL ON TABLE {table} FROM {APP_ROLE}"))
    op.drop_column("incident", "password_hash")
    op.drop_table("join_code")
    op.drop_index("ix_credential_device_id", table_name="device_credential")
    op.drop_index("ix_credential_token_hash", table_name="device_credential")
    op.drop_table("device_credential")
