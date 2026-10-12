"""Redis fixed-window rate limiter (keyed by bucket + client IP + route).

Usage as a router/endpoint dependency::

    router = APIRouter(dependencies=[Depends(rate_limit("auth"))])

The limit for a bucket is resolved from settings at request time, so tests can
build an app with a tiny limit without monkeypatching.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.errors import AppError

KEY_PREFIX = "rl"


class RateLimited(AppError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(
            "rate_limited",
            "Too many requests, please try again later",
            status_code=429,
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


async def hit(redis: Redis, key: str, limit: int, window: int) -> tuple[bool, int]:
    """Count one hit in the current window. Returns (allowed, retry_after_seconds)."""
    now = int(time.time())
    window_start = now - now % window
    bucket_key = f"{KEY_PREFIX}:{key}:{window_start}"
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incr(bucket_key)
        pipe.expire(bucket_key, window + 1)
        count, _ = await pipe.execute()
    retry_after = window_start + window - now
    return int(count) <= limit, max(retry_after, 1)


def _limit_for(settings: Settings, bucket: str) -> tuple[int, int]:
    if bucket == "auth":
        return settings.auth_rate
    raise ValueError(f"unknown rate-limit bucket {bucket!r}")


def rate_limit(bucket: str) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        settings: Settings = request.app.state.settings
        redis: Redis = request.app.state.redis
        limit, window = _limit_for(settings, bucket)
        client_ip = request.client.host if request.client else "unknown"
        key = f"{bucket}:{client_ip}:{request.url.path}"
        allowed, retry_after = await hit(redis, key, limit, window)
        if not allowed:
            raise RateLimited(retry_after)

    return dependency
