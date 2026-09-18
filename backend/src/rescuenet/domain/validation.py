"""Rejection codes and their classification (docs/09 §2.6, §2.6.1, §2.6.2).

M2 defines the vocabulary and the severity partition. *Applying* codes during
ingestion belongs to M3/M4 — the codes that need server context
(``SEQ_NOT_MONOTONIC``, ``ATTRIBUTION_MISMATCH``, ``WRONG_INCIDENT``,
``UNKNOWN_CELL``, ``TYPE_NOT_PERMITTED``, ``UNAVAILABLE``) cannot be decided
from a single event in isolation.
"""

from __future__ import annotations

from enum import Enum


class RejectionCode(str, Enum):
    """docs/09 §2.6. Codes are diagnostics; clients act on ``retryable`` (AP-21)."""

    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    UNKNOWN_CELL = "UNKNOWN_CELL"
    SEQ_NOT_MONOTONIC = "SEQ_NOT_MONOTONIC"
    ATTRIBUTION_MISMATCH = "ATTRIBUTION_MISMATCH"
    WRONG_INCIDENT = "WRONG_INCIDENT"
    TYPE_NOT_PERMITTED = "TYPE_NOT_PERMITTED"
    UNAVAILABLE = "UNAVAILABLE"


class CodeClass(str, Enum):
    """docs/09 §2.6.2 severity partition."""

    #: The event cannot be parsed or stored meaningfully. Applies to all types.
    STRUCTURAL = "STRUCTURAL"
    #: Accepting would corrupt the audit record. Applies to all types.
    SECURITY = "SECURITY"
    #: Well-formed but points at something unknown. ROUTINE types only.
    REFERENCE = "REFERENCE"
    #: Transient.
    TRANSIENT = "TRANSIENT"


_CLASS_OF: dict[RejectionCode, CodeClass] = {
    RejectionCode.UNKNOWN_TYPE: CodeClass.STRUCTURAL,
    RejectionCode.UNSUPPORTED_SCHEMA: CodeClass.STRUCTURAL,
    RejectionCode.INVALID_PAYLOAD: CodeClass.STRUCTURAL,
    RejectionCode.ATTRIBUTION_MISMATCH: CodeClass.SECURITY,
    RejectionCode.WRONG_INCIDENT: CodeClass.SECURITY,
    RejectionCode.TYPE_NOT_PERMITTED: CodeClass.SECURITY,
    RejectionCode.SEQ_NOT_MONOTONIC: CodeClass.SECURITY,
    RejectionCode.UNKNOWN_CELL: CodeClass.REFERENCE,
    RejectionCode.UNAVAILABLE: CodeClass.TRANSIENT,
}


def code_class(code: RejectionCode) -> CodeClass:
    return _CLASS_OF[code]


def is_retryable(code: RejectionCode) -> bool:
    """Only ``UNAVAILABLE`` is retryable (docs/09 §2.6)."""
    return code_class(code) is CodeClass.TRANSIENT


def may_permanently_reject(code: RejectionCode, priority: "Priority") -> bool:  # noqa: F821
    """AP-20 — may this code permanently reject an event of this priority?

    A ``SURVIVOR_REPORTED`` with a mistyped ``cell_index`` must never be lost:
    reference errors do not reject CRITICAL events, which are accepted and
    flagged instead. Structural and security errors still apply to every type.
    """
    from rescuenet.domain.enums import Priority

    if priority is Priority.CRITICAL and code_class(code) is CodeClass.REFERENCE:
        return False
    return not is_retryable(code)


class EventValidationError(ValueError):
    """A canonical event failed structural validation."""

    def __init__(self, code: RejectionCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
