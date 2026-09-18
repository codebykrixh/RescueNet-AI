"""The single error shape (docs/09 Part 9).

One structure everywhere. ``retryable`` is the field clients act on; ``code`` is
a stable machine-readable string and ``message`` is for humans (AP-21).
"""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    """An error the contract defines. Rendered by the handler in ``api.errors``."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def body(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "retryable": self.retryable,
                "details": self.details,
            }
        }


def bad_request(code: str, message: str, **details) -> ApiError:
    return ApiError(400, code, message, details=details)


def not_found(code: str, message: str, **details) -> ApiError:
    return ApiError(404, code, message, details=details)


def conflict(code: str, message: str, **details) -> ApiError:
    return ApiError(409, code, message, details=details)


def unprocessable(code: str, message: str, **details) -> ApiError:
    return ApiError(422, code, message, details=details)


def unavailable(message: str = "dependency unavailable", **details) -> ApiError:
    """The only retryable class (docs/09 §2.6)."""
    return ApiError(503, "UNAVAILABLE", message, retryable=True, details=details)
