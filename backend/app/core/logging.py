"""structlog JSON logging + request-id middleware.

Every log line emitted while a request is being handled carries `request_id`
(and `user_id` once authentication has resolved the caller).
"""

from __future__ import annotations

import logging
import sys
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"


def configure_logging(level: str = "INFO") -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    structlog.configure(
        processors=[
            *shared,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,
    )
    logging.basicConfig(level=level.upper(), format="%(message)s", stream=sys.stdout)


def bind_user(user_id: str) -> None:
    structlog.contextvars.bind_contextvars(user_id=user_id)


class RequestContextMiddleware:
    """Pure ASGI middleware (works for both HTTP and WebSocket scopes)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self.log = structlog.get_logger("http")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        incoming = dict(scope.get("headers") or []).get(REQUEST_ID_HEADER.encode())
        request_id = incoming.decode()[:128] if incoming else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.perf_counter()
        status_code = 0

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((REQUEST_ID_HEADER.encode(), request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if scope["type"] == "http":
                self.log.info(
                    "request",
                    method=scope.get("method"),
                    path=scope.get("path"),
                    status=status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 1),
                )
            structlog.contextvars.clear_contextvars()
