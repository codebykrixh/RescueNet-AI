"""M1: typed configuration and its validation (docs/12 M1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from rescuenet.config.settings import AppEnv, Settings

pytestmark = pytest.mark.unit


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


def test_defaults_are_safe_for_development():
    s = _settings()
    assert s.app_env is AppEnv.DEV
    assert s.backend_port == 8000


def test_no_secret_has_a_default_value():
    """Nothing sensitive may be hard-coded (docs/12 M1 configuration rules)."""
    s = _settings()
    assert s.database_url is None
    assert s.mqtt_password is None
    assert s.mqtt_username is None


def test_secrets_are_not_exposed_by_repr():
    s = _settings(database_url="postgresql://u:hunter2@h/db",
                  mqtt_password="s3cret-broker-pw")
    blob = f"{s!r} {s}"
    assert "hunter2" not in blob
    assert "s3cret-broker-pw" not in blob


def test_secret_value_is_retrievable_when_explicitly_asked():
    s = _settings(mqtt_password="s3cret-broker-pw")
    assert s.mqtt_password.get_secret_value() == "s3cret-broker-pw"


def test_production_requires_database_and_broker():
    with pytest.raises(ValidationError) as err:
        _settings(app_env="prod")
    message = str(err.value)
    assert "RESCUENET_DATABASE_URL" in message
    assert "RESCUENET_MQTT_HOST" in message


def test_production_accepts_a_complete_configuration():
    s = _settings(app_env="prod", database_url="postgresql://u:p@h/db",
                  mqtt_host="mosquitto")
    assert s.app_env is AppEnv.PROD


def test_invalid_log_level_is_rejected():
    with pytest.raises(ValidationError):
        _settings(log_level="CHATTY")


def test_log_level_is_normalised():
    assert _settings(log_level="debug").log_level == "DEBUG"


def test_port_range_is_validated():
    with pytest.raises(ValidationError):
        _settings(backend_port=70000)


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("RESCUENET_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("RESCUENET_BACKEND_PORT", "9999")
    s = Settings(_env_file=None)
    assert s.log_level == "WARNING"
    assert s.backend_port == 9999
