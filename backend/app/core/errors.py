"""Uniform error envelope: every error response is `{code, message, details}`."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger(__name__)

_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    503: "service_unavailable",
}


class AppError(Exception):
    """Domain error raised by services; rendered by `app_error_handler`."""

    status_code = 400

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        details: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
        if status_code is not None:
            self.status_code = status_code


class NotFound(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__("not_found", message, status_code=404)


class Unauthorized(AppError):
    def __init__(self, code: str = "unauthorized", message: str = "Not authenticated") -> None:
        super().__init__(code, message, status_code=401)


class Conflict(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, status_code=409)


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "details": details}


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        error_body(exc.code, exc.message, exc.details),
        status_code=exc.status_code,
        headers=exc.headers,
    )


async def http_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    code = _STATUS_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else code
    return JSONResponse(error_body(code, message), status_code=exc.status_code, headers=exc.headers)


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        {
            "loc": list(err.get("loc", ())),
            "msg": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "Request validation failed", jsonable_encoder(details)),
        status_code=422,
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", exc_info=exc)
    return JSONResponse(error_body("internal_error", "Internal server error"), status_code=500)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
