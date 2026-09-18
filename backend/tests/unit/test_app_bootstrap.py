"""M1: application startup/shutdown wiring and fixture harness."""

from __future__ import annotations

import pytest

from rescuenet.app import create_app

pytestmark = pytest.mark.unit


def test_app_factory_builds_an_application(settings):
    app = create_app(settings)
    assert app.title == "RescueNet AI"


def test_settings_are_attached_to_app_state(settings):
    assert create_app(settings).state.settings is settings


def test_lifespan_runs_startup_and_shutdown(settings):
    from fastapi.testclient import TestClient

    with TestClient(create_app(settings)) as c:
        assert c.get("/health").status_code == 200


def test_openapi_schema_generates(client):
    schema = client.get("/openapi.json").json()
    assert schema["info"]["title"] == "RescueNet AI"
    assert "/health" in schema["paths"]


def test_shared_fixtures_directory_is_the_canonical_location(shared_fixtures_dir):
    """docs/12 §3: one fixture location, consumed by all three suites."""
    assert shared_fixtures_dir.is_dir()
    assert shared_fixtures_dir.name == "fixtures"
    assert shared_fixtures_dir.parent.name == "shared"


def test_no_duplicate_fixture_directory_inside_backend():
    """Backend must not fork canonical fixtures (audit F-13)."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    assert not (backend / "tests" / "fixtures").exists()


def test_missing_fixture_raises_a_directive_error(load_shared_fixture):
    """At M1 the directory is empty; the error must point to M2, not invite a copy."""
    with pytest.raises(FileNotFoundError, match="do not create a local copy"):
        load_shared_fixture("does-not-exist-yet.json")
