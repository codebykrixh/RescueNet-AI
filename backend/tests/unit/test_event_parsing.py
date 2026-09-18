"""parse_event maps failures to docs/09 §2.6 rejection codes; AP-20 partition."""
from __future__ import annotations

import pytest

from rescuenet.domain import (
    CodeClass, EventValidationError, Priority, RejectionCode, code_class,
    is_retryable, may_permanently_reject, parse_event,
)

pytestmark = pytest.mark.unit


def test_valid_event_parses(raw_event):
    assert parse_event(raw_event()).type.value == "CELL_STATUS_REPORTED"


def test_unknown_type_yields_unknown_type(raw_event):
    with pytest.raises(EventValidationError) as e:
        parse_event(raw_event(type="TELEPORTED"))
    assert e.value.code is RejectionCode.UNKNOWN_TYPE


def test_future_schema_version_yields_unsupported_schema(raw_event):
    with pytest.raises(EventValidationError) as e:
        parse_event(raw_event(schema_version=99))
    assert e.value.code is RejectionCode.UNSUPPORTED_SCHEMA


def test_malformed_payload_yields_invalid_payload(raw_event):
    with pytest.raises(EventValidationError) as e:
        parse_event(raw_event(payload={"nope": 1}))
    assert e.value.code is RejectionCode.INVALID_PAYLOAD


def test_missing_required_field_yields_invalid_payload(raw_event):
    raw = raw_event(); raw.pop("team_id")
    with pytest.raises(EventValidationError) as e:
        parse_event(raw)
    assert e.value.code is RejectionCode.INVALID_PAYLOAD


def test_non_object_yields_invalid_payload():
    with pytest.raises(EventValidationError) as e:
        parse_event(["not", "an", "object"])
    assert e.value.code is RejectionCode.INVALID_PAYLOAD


def test_all_nine_codes_from_docs09_exist():
    assert {c.value for c in RejectionCode} == {
        "UNKNOWN_TYPE", "UNSUPPORTED_SCHEMA", "INVALID_PAYLOAD", "UNKNOWN_CELL",
        "SEQ_NOT_MONOTONIC", "ATTRIBUTION_MISMATCH", "WRONG_INCIDENT",
        "TYPE_NOT_PERMITTED", "UNAVAILABLE",
    }


def test_only_unavailable_is_retryable():
    retryable = [c for c in RejectionCode if is_retryable(c)]
    assert retryable == [RejectionCode.UNAVAILABLE]


@pytest.mark.parametrize(
    "code,expected",
    [(RejectionCode.UNKNOWN_TYPE, CodeClass.STRUCTURAL),
     (RejectionCode.INVALID_PAYLOAD, CodeClass.STRUCTURAL),
     (RejectionCode.ATTRIBUTION_MISMATCH, CodeClass.SECURITY),
     (RejectionCode.WRONG_INCIDENT, CodeClass.SECURITY),
     (RejectionCode.UNKNOWN_CELL, CodeClass.REFERENCE),
     (RejectionCode.UNAVAILABLE, CodeClass.TRANSIENT)],
)
def test_severity_partition(code, expected):
    assert code_class(code) is expected


def test_ap20_reference_error_never_permanently_rejects_a_critical_event():
    """A mistyped cell_index must not discard a real survivor's location."""
    assert not may_permanently_reject(RejectionCode.UNKNOWN_CELL, Priority.CRITICAL)
    assert may_permanently_reject(RejectionCode.UNKNOWN_CELL, Priority.ROUTINE)


@pytest.mark.parametrize(
    "code", [RejectionCode.UNKNOWN_TYPE, RejectionCode.INVALID_PAYLOAD,
             RejectionCode.ATTRIBUTION_MISMATCH, RejectionCode.WRONG_INCIDENT],
)
def test_structural_and_security_errors_reject_every_priority(code):
    assert may_permanently_reject(code, Priority.CRITICAL)
    assert may_permanently_reject(code, Priority.ROUTINE)


def test_transient_errors_never_permanently_reject():
    for p in Priority:
        assert not may_permanently_reject(RejectionCode.UNAVAILABLE, p)
