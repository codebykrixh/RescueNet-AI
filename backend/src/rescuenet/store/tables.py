"""Physical schema (docs/08 §11.1 and §11.2).

SQLAlchemy Core only — no ORM mapping of the canonical event. The canonical
event lives in ``rescuenet.domain`` and is not duplicated here; these tables are
its storage representation and the storage representation of the read models
derived from it.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()

# ─────────────────────────── SOURCE OF TRUTH ────────────────────────────────
#: The only authoritative operational table (docs/08 §11.1, AD-01, AD-04).
#: Append-only: the application role holds INSERT and SELECT only (DM-29).
event = Table(
    "event",
    metadata,
    Column("device_id", Integer, primary_key=True, nullable=False),
    Column("seq", BigInteger, primary_key=True, nullable=False),
    Column("server_seq", BigInteger, Identity(always=True), nullable=False),
    Column("incident_id", Integer, nullable=False),
    Column("type", SmallInteger, nullable=False),
    Column("entity_type", SmallInteger, nullable=False),
    Column("entity_id", BigInteger, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("t_dev", DateTime(timezone=True), nullable=False),
    Column("t_srv", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("schema_version", SmallInteger, nullable=False),
    Column("responder_id", Integer, nullable=False),
    Column("team_id", Integer, nullable=False),
    Column("agency_id", Integer, nullable=False),
    Column("received_via", SmallInteger, nullable=True),
    UniqueConstraint("server_seq", name="uq_event_server_seq"),
    # docs/08 §11.1 index list
    Index("ix_event_server_seq", "server_seq"),
    Index("ix_event_incident_server_seq", "incident_id", "server_seq"),
    Index("ix_event_entity_server_seq", "entity_type", "entity_id", "server_seq"),
    Index("ix_event_team_server_seq", "team_id", "server_seq"),
    Index("ix_event_type_incident", "type", "incident_id"),
)

# ──────────────── REFERENCE TABLES — M4-owned (docs/08 §11.1, docs/12 §3.1) ──
# Source of truth, not event-derived. `device_credential` and `join_code` are
# M5-owned (docs/12 §3.2) and are deliberately absent here.

incident = Table(
    "incident", metadata,
    Column("incident_id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), nullable=False),
    Column("disaster_type", String(32), nullable=False),
    Column("origin_lat", Float, nullable=False),
    Column("origin_lon", Float, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("notes", String(1000), nullable=True),
    # M5, docs/08 §11.1c — scrypt$params$salt$hash. Plaintext never stored.
    Column("password_hash", String(512), nullable=True),
)

agency = Table(
    "agency", metadata,
    Column("agency_id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(120), nullable=False),
    Column("agency_type", String(64), nullable=False),
)

resource_item = Table(
    "resource_item", metadata,
    Column("item_id", Integer, primary_key=True, autoincrement=False),
    Column("name", String(120), nullable=False),
    Column("category", String(32), nullable=False),
)

#: Team registry — written by endpoint 5, read by the snapshot. Derived from
#: TEAM_REGISTERED events via `team_state`; this table holds nothing extra.

# ─────────── CREDENTIAL TABLES — M5-owned (docs/08 §11.1a/§11.1b) ───────────
# Never in the event log (DM-11). Secrets live here and nowhere else.

device_credential = Table(
    "device_credential", metadata,
    # Surrogate PK: a COMMANDER session is not a device and must not consume a
    # device_id from the 1..4095 space TR-22 reserves for handsets (DM-50).
    Column("credential_id", BigInteger, primary_key=True, autoincrement=True),
    Column("device_id", Integer, nullable=True, unique=True),
    Column("token_hash", String(128), nullable=False, unique=True),
    Column("hmac_secret", LargeBinary, nullable=True),
    Column("role", String(16), nullable=False),
    Column("incident_id", Integer, nullable=True),
    Column("issued_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("revoked_at", DateTime(timezone=True), nullable=True),
)

join_code = Table(
    "join_code", metadata,
    Column("code", String(16), primary_key=True),
    Column("team_id", Integer, nullable=False),
    Column("incident_id", Integer, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("max_uses", Integer, nullable=False),
    Column("uses", Integer, nullable=False, server_default="0"),
)

CREDENTIAL_TABLES = (device_credential, join_code)

# ───────────────────── DERIVED READ MODELS (docs/08 §11.2) ──────────────────
# Every one of these is disposable and rebuildable from `event` alone (DM-30).

cell_state = Table(
    "cell_state", metadata,
    Column("incident_id", Integer, primary_key=True),
    Column("cell_index", Integer, primary_key=True),
    Column("status", String(32), nullable=False),
    Column("team_id", Integer, nullable=True),
    Column("last_server_seq", BigInteger, nullable=True),
)

duplicate_search = Table(
    "duplicate_search", metadata,
    Column("incident_id", Integer, primary_key=True),
    Column("cell_index", Integer, primary_key=True),
    Column("team_count", Integer, nullable=False),
    Column("team_ids", JSONB, nullable=False),
)

assignment_state = Table(
    "assignment_state", metadata,
    Column("incident_id", Integer, primary_key=True),
    Column("cell_index", Integer, primary_key=True),
    Column("team_id", Integer, nullable=True),
    Column("assignment_id", BigInteger, nullable=True),
    Column("last_server_seq", BigInteger, nullable=False),
)

team_state = Table(
    "team_state", metadata,
    Column("team_id", Integer, primary_key=True),
    Column("callsign", String(64), nullable=True),
    Column("agency_id", Integer, nullable=True),
    Column("status", String(32), nullable=True),
    Column("last_server_seq", BigInteger, nullable=True),
)

team_position = Table(
    "team_position", metadata,
    Column("team_id", Integer, primary_key=True),
    Column("rel_lat", Integer, nullable=False),
    Column("rel_lon", Integer, nullable=False),
    Column("t_srv", DateTime(timezone=True), nullable=True),
    Column("last_server_seq", BigInteger, nullable=False),
)

resource_stock = Table(
    "resource_stock", metadata,
    Column("team_id", Integer, primary_key=True),
    Column("item_id", Integer, primary_key=True),
    Column("qty", Integer, nullable=False),
)

survivor_report = Table(
    "survivor_report", metadata,
    Column("device_id", Integer, primary_key=True),
    Column("seq", BigInteger, primary_key=True),
    Column("incident_id", Integer, nullable=False),
    Column("cell_index", Integer, nullable=False),
    Column("person_count", Integer, nullable=False),
    Column("survivor_status", String(32), nullable=False),
    Column("triage", String(16), nullable=True),
    Column("team_id", Integer, nullable=False),
    Column("agency_id", Integer, nullable=False),
    Column("unresolved_cell", Boolean, nullable=False, server_default="false"),
    Column("server_seq", BigInteger, nullable=True),
)

#: AP-24 — server-owned, single fold, derived from cell_state + grid rows x cols.
coverage_metrics = Table(
    "coverage_metrics", metadata,
    Column("incident_id", Integer, primary_key=True),
    Column("total", Integer, nullable=False),
    Column("searched", Integer, nullable=False),
    Column("in_progress", Integer, nullable=False),
    Column("needs_research", Integer, nullable=False),
    Column("assigned", Integer, nullable=False),
    Column("unsearched", Integer, nullable=False),
)

#: Singleton watermark for incremental folding and rebuild.
projection_state = Table(
    "projection_state", metadata,
    Column("id", SmallInteger, primary_key=True),
    Column("last_projected_server_seq", BigInteger, nullable=False, server_default="0"),
)

#: Reference tables (M4). Source of truth, never rebuilt from the event log.
REFERENCE_TABLES = (incident, agency, resource_item)

#: Read models only — everything the projection engine may rewrite.
READ_MODELS = (
    cell_state, duplicate_search, assignment_state, team_state, team_position,
    resource_stock, survivor_report, coverage_metrics, projection_state,
)
