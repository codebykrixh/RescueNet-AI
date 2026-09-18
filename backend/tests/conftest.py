"""pytest harness (docs/12 M1, docs/11 §2).

Canonical fixtures live in ``shared/fixtures/`` and nowhere else (docs/12 §3).
This module exposes that one location to the backend suite; it does not copy
anything, because three independently-written fixture sets would drift and one
cannot (audit finding F-13).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

#: The ambient ``RESCUENET_DATABASE_URL``, captured at collection time — before
#: any per-test isolation clears it. Host-run work exports this from
#: ``deploy/.env``'s ``DATABASE_URL_HOST`` (see README). M3 integration tests
#: read it from here; when it is absent they skip rather than fabricate.
AMBIENT_DATABASE_URL = os.environ.get("RESCUENET_DATABASE_URL")

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_FIXTURES = REPO_ROOT / "shared" / "fixtures"


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch):
    """Unit tests must be deterministic regardless of the developer's shell.

    Running host-side tooling requires exporting ``RESCUENET_DATABASE_URL``
    (README). Without this fixture that export silently changes the result of
    configuration unit tests, which assert on *defaults*. Clearing every
    ``RESCUENET_*`` variable makes the suite independent of the environment it
    happens to run in; tests that want a variable set it explicitly afterwards
    with ``monkeypatch.setenv``, which still applies.
    """
    for key in [k for k in os.environ if k.startswith("RESCUENET_")]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(scope="session")
def database_url() -> str | None:
    """Host-facing database URL for integration tests, or ``None`` if unset.

    Provided for M3. Not used by any unit test.
    """
    return AMBIENT_DATABASE_URL


@pytest.fixture(scope="session")
def shared_fixtures_dir() -> Path:
    """The single canonical fixture location."""
    return SHARED_FIXTURES


@pytest.fixture(scope="session")
def load_shared_fixture():
    """Load a canonical fixture by filename from ``shared/fixtures/``.

    The directory is populated at M2 from docs/08 Part 16. At M1 the wiring
    exists and is tested; the fixtures themselves do not yet.
    """

    def _load(name: str):
        path = SHARED_FIXTURES / name
        if not path.exists():
            raise FileNotFoundError(
                f"canonical fixture {name!r} not found in {SHARED_FIXTURES}. "
                "Fixtures are added at M2 — do not create a local copy."
            )
        return json.loads(path.read_text(encoding="utf-8"))

    return _load


@pytest.fixture
def settings():
    """Test settings, independent of the developer's environment."""
    from rescuenet.config.settings import AppEnv, Settings

    return Settings(app_env=AppEnv.TEST, log_level="INFO", _env_file=None)


@pytest.fixture
def client(settings):
    """TestClient over the application factory."""
    from fastapi.testclient import TestClient

    from rescuenet.app import create_app

    with TestClient(create_app(settings)) as test_client:
        yield test_client


# ---------------------------------------------------------------- M2 factories
@pytest.fixture
def raw_event(load_shared_fixture):
    """A canonical event as a plain dict, seeded from the shared fixture.

    Derived from the canonical file at runtime — never a forked copy (F-13).
    """

    def _raw(**overrides):
        base = load_shared_fixture("cell_status_reported.json")
        base.update(overrides)
        return base

    return _raw


@pytest.fixture
def canonical_event(raw_event):
    """A parsed :class:`CanonicalEvent`, overridable per test."""
    from rescuenet.domain import CanonicalEvent

    def _event(**overrides):
        return CanonicalEvent(**raw_event(**overrides))

    return _event


@pytest.fixture(scope="session")
def all_fixture_files(shared_fixtures_dir):
    return sorted(shared_fixtures_dir.glob("*.json"))
