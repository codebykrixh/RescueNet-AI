"""Integration fixtures — require a live PostgreSQL (docs/11 level I).

The database URL comes from ``RESCUENET_DATABASE_URL``, captured at collection
time by the root conftest. When it is absent these tests **skip** with a clear
message rather than pass vacuously or fabricate a result.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import AMBIENT_DATABASE_URL

pytestmark = pytest.mark.integration

#: Every shared fixture in shared/fixtures/ belongs to this incident.
FIXTURE_INCIDENT_ID = 9

_SKIP = (
    "RESCUENET_DATABASE_URL is not set — integration tests need a live database.\n"
    '  export RESCUENET_DATABASE_URL="$(grep \'^DATABASE_URL_HOST=\' '
    'deploy/.env | cut -d= -f2-)"'
)


@pytest.fixture(scope="session")
def owner_engine():
    """Engine as the database owner — schema setup and negative controls."""
    if not AMBIENT_DATABASE_URL:
        pytest.skip(_SKIP)
    from rescuenet.store import make_engine

    engine = make_engine(AMBIENT_DATABASE_URL, assume_role=False)
    with engine.connect() as conn:
        if not conn.execute(text("select to_regclass('public.event')")).scalar():
            pytest.skip("schema absent — run `alembic upgrade head` first")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine(owner_engine):
    """Engine under the restricted ``rescuenet_app`` role — how the app connects."""
    from rescuenet.store import make_engine

    engine = make_engine(AMBIENT_DATABASE_URL, assume_role=True)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_db(owner_engine):
    """Empty every table before each test. Owner rights, never the app role.

    Reference tables are included: since M4 they hold rows, and `event` carries
    a foreign key to `incident`, so they must be truncated together.
    """
    from rescuenet.store.tables import READ_MODELS, REFERENCE_TABLES

    names = [t.name for t in READ_MODELS] + ["event"] + [t.name for t in REFERENCE_TABLES]
    with owner_engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {', '.join(names)} RESTART IDENTITY CASCADE"))
        # Since M4 the event table carries `fk_event_incident` (docs/08 §11.1).
        # The shared fixtures all belong to incident 9, so it must exist for any
        # append to succeed. Seeded here rather than relaxing the constraint —
        # referential integrity is a documented requirement, not test friction.
        conn.execute(text(
            "INSERT INTO incident (incident_id, name, disaster_type, origin_lat,"
            " origin_lon, started_at) VALUES (:i, :n, :d, :la, :lo, now())"
            " ON CONFLICT (incident_id) DO NOTHING"
        ), {"i": FIXTURE_INCIDENT_ID, "n": "Fixture Incident",
            "d": "LANDSLIDE", "la": 19.1638, "lo": 73.6822})
    return owner_engine


#: The bootstrap incident password, provisioned out-of-band exactly as an
#: operator would. See the M5 report: `09` makes endpoint 3 Session-authenticated
#: while a session requires an existing incident, so the first incident cannot be
#: created through the API. Tests mirror the operational provisioning step.
BOOTSTRAP_PASSWORD = "readiness-only-not-a-real-secret"


@pytest.fixture
def anon_api(clean_db, app_engine):
    """TestClient with **no credentials** — for authentication negative controls."""
    from fastapi.testclient import TestClient

    from rescuenet.app import create_app
    from rescuenet.config.settings import AppEnv, Settings

    app = create_app(Settings(app_env=AppEnv.TEST, _env_file=None))
    with TestClient(app) as client:
        # Assign AFTER startup: the lifespan sets state.engine from settings.
        app.state.engine = app_engine
        yield client


@pytest.fixture
def bootstrap_incident(clean_db, owner_engine):
    """Incident 9 with a password, provisioned directly (operational bootstrap)."""
    from rescuenet.services.credentials import hash_password

    with owner_engine.begin() as conn:
        conn.execute(text(
            "UPDATE incident SET password_hash = :h WHERE incident_id = :i"
        ), {"h": hash_password(BOOTSTRAP_PASSWORD), "i": FIXTURE_INCIDENT_ID})
    return FIXTURE_INCIDENT_ID


@pytest.fixture
def commander(anon_api, bootstrap_incident):
    """An authenticated COMMANDER session scoped to the bootstrap incident."""
    r = anon_api.post("/v1/auth/session", json={
        "incident_id": bootstrap_incident, "password": BOOTSTRAP_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def api(anon_api, commander):
    """TestClient authenticated as COMMANDER — the default for M4 endpoints."""
    anon_api.headers.update({"Authorization": f"Bearer {commander}"})
    return anon_api


@pytest.fixture
def incident(bootstrap_incident):
    """The incident every M4 endpoint test operates on."""
    return bootstrap_incident


@pytest.fixture
def field_device(api, incident):
    """An enrolled FIELD device: returns (token, device_id, team_id)."""
    code = api.post(f"/v1/teams/3/join-code",
                    json={"incident_id": incident}).json()["join_code"]
    r = api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"})
    assert r.status_code == 201, r.text
    b = r.json()
    return b["token"], b["device_id"], b["team_id"]


@pytest.fixture
def gateway_device(api, incident):
    """An enrolled GATEWAY device: returns (token, device_id)."""
    code = api.post(f"/v1/teams/3/join-code",
                    json={"incident_id": incident}).json()["join_code"]
    r = api.post("/v1/enrol", json={"join_code": code, "mode": "GATEWAY"})
    assert r.status_code == 201, r.text
    return r.json()["token"], r.json()["device_id"]


@pytest.fixture
def gridded(api, incident):
    """An incident with a 25x200 grid (5,000 cells — the NFR-09 target)."""
    r = api.post(f"/v1/incidents/{incident}/grid", json={
        "origin_lat": 19.1638, "origin_lon": 73.6822, "cell_size_m": 100.0,
        "rows": 25, "cols": 200, "bearing_deg": 0.0,
    })
    assert r.status_code == 201, r.text
    return incident


@pytest.fixture
def device_api(anon_api, field_device):
    """A second client authenticated as the enrolled FIELD device.

    `POST /v1/events` is `Device or Gateway` (docs/09 §1.1), so a COMMANDER
    session is correctly refused there — event tests must use this client.
    """
    from fastapi.testclient import TestClient

    token, device_id, team_id = field_device
    client = TestClient(anon_api.app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    client.device_id, client.team_id = device_id, team_id
    return client


@pytest.fixture
def second_device_api(anon_api, api, incident):
    """A second enrolled FIELD device on a different team — for duplicate search."""
    from fastapi.testclient import TestClient

    code = api.post("/v1/teams/5/join-code",
                    json={"incident_id": incident}).json()["join_code"]
    b = api.post("/v1/enrol", json={"join_code": code, "mode": "FIELD"}).json()
    client = TestClient(anon_api.app)
    client.headers.update({"Authorization": f"Bearer {b['token']}"})
    client.device_id, client.team_id = b["device_id"], b["team_id"]
    return client
