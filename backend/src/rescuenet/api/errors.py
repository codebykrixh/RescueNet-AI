"""Error rendering (docs/09 Part 9).

Every failure leaves the API in the one documented shape. FastAPI's own
validation errors are translated too, so a client never sees a raw Pydantic
error where the contract specifies a structured application error.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from rescuenet.services.errors import ApiError

_STATUS_CODE = {
    400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN",
    404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE", 422: "INVALID_PAYLOAD", 500: "INTERNAL",
    503: "UNAVAILABLE",
}


def _body(code: str, message: str, retryable: bool, details: dict) -> dict:
    return {"error": {"code": code, "message": message,
                      "retryable": retryable, "details": details}}


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # docs/09 §9.2: well-formed but semantically invalid -> 422, and only
        # 500/503 are retryable.
        return JSONResponse(
            status_code=422,
            content=_body("INVALID_PAYLOAD", "request failed validation",
                          False, {"errors": exc.errors()[:10]}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODE.get(exc.status_code, "ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(code, str(exc.detail), exc.status_code in (500, 503), {}),
        )
