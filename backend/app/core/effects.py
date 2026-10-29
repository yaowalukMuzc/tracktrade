"""Side effects of a write — realtime events and background jobs — run after the commit.

Services take an `Effects` instead of reaching for Redis themselves, so the same code runs in an
HTTP request (`get_effects`), in the ingest endpoint and in arq jobs (`Effects.from_worker`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from arq.connections import ArqRedis
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import after_commit
from app.core.pubsub import publish


@dataclass(frozen=True, slots=True)
class Effects:
    redis: Redis
    queue: ArqRedis | None = None

    def publish(
        self, session: AsyncSession, user_id: uuid.UUID, type_: str, data: Any = None
    ) -> None:
        async def run() -> None:
            await publish(self.redis, user_id, type_, data)

        after_commit(session, run)

    def enqueue(
        self, session: AsyncSession, function: str, *args: Any, job_id: str | None = None
    ) -> None:
        """`job_id` de-duplicates: while a job with that id is queued, a second one is dropped."""
        queue = self.queue
        if queue is None:
            return

        async def run() -> None:
            await queue.enqueue_job(function, *args, _job_id=job_id)

        after_commit(session, run)

    @classmethod
    def from_worker(cls, ctx: dict[str, Any]) -> Effects:
        redis: ArqRedis = ctx["redis"]
        return cls(redis=redis, queue=redis)


def get_effects(request: Request) -> Effects:
    return Effects(redis=request.app.state.redis, queue=request.app.state.queue)
