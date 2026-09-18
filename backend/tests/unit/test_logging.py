"""M1: structured JSON logging and credential redaction (docs/07 T-19)."""

from __future__ import annotations

import json
import logging

import pytest

from rescuenet.config.logging import REDACTED, JsonFormatter, configure_logging, redact

pytestmark = pytest.mark.unit


def _emit(**extra) -> dict:
    record = logging.LogRecord(
        name="rescuenet.test", level=logging.INFO, pathname=__file__,
        lineno=1, msg="event happened", args=(), exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return json.loads(JsonFormatter().format(record))


def test_output_is_one_json_object():
    payload = _emit()
    assert payload["message"] == "event happened"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "rescuenet.test"
    assert "ts" in payload


def test_structured_extras_are_included():
    assert _emit(incident_id=9)["incident_id"] == 9


@pytest.mark.parametrize(
    "field",
    ["password", "mqtt_password", "DB_PASSWORD", "api_key", "token",
     "authorization", "hmac_secret", "database_url", "device_credential"],
)
def test_sensitive_fields_are_redacted(field):
    assert _emit(**{field: "super-secret-value"})[field] == REDACTED


def test_redaction_reaches_nested_structures():
    out = redact({"outer": {"mqtt_password": "pw", "keep": 1},
                  "list": [{"token": "t"}]})
    assert out["outer"]["mqtt_password"] == REDACTED
    assert out["outer"]["keep"] == 1
    assert out["list"][0]["token"] == REDACTED


def test_non_sensitive_fields_survive():
    assert _emit(team_id=3, cell_index=214)["team_id"] == 3


def test_configure_logging_installs_a_single_json_handler():
    configure_logging("INFO")
    root = logging.getLogger()
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JsonFormatter)
    configure_logging("INFO")           # idempotent
    assert len(logging.getLogger().handlers) == 1


def test_exceptions_are_captured():
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="t", level=logging.ERROR, pathname=__file__, lineno=1,
            msg="failed", args=(), exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]
