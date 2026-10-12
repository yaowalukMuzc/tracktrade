"""`GET /api/v1/health` — DB + Redis liveness (used by the docker healthcheck)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.errors import error_body

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_S = 2.0


async def _check_db(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis(redis: Redis) -> None:
    await redis.ping()


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    checks: dict[str, str] = {}
    for name, coro in (
        ("db", _check_db(request.app.state.engine)),
        ("redis", _check_redis(request.app.state.redis)),
    ):
        try:
            await asyncio.wait_for(coro, CHECK_TIMEOUT_S)
            checks[name] = "ok"
        except Exception as exc:
            checks[name] = f"error: {type(exc).__name__}"
    if all(v == "ok" for v in checks.values()):
        return JSONResponse({"status": "ok"})
    return JSONResponse(
        error_body("service_unavailable", "Dependency check failed", checks), status_code=503
    )
