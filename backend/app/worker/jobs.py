"""arq job functions. Each receives arq's `ctx` (contains `redis`) first."""

from __future__ import annotations

from typing import Any

import structlog
from arq import Retry

from app.core.pubsub import publish

log = structlog.get_logger(__name__)

BACKOFF_BASE_S = 5


def retry_with_backoff(ctx: dict[str, Any]) -> Retry:
    """Exponential backoff for transient failures: `raise retry_with_backoff(ctx)`.

    Tries are capped by `WorkerSettings.max_tries` (5s, 10s, 20s ...).
    """
    job_try = int(ctx.get("job_try", 1))
    return Retry(defer=BACKOFF_BASE_S * 2 ** (job_try - 1))


async def ping(ctx: dict[str, Any], user_id: str) -> str:
    """Round-trip check: worker -> Redis pub/sub -> API hub -> user's sockets."""
    receivers = await publish(ctx["redis"], user_id, "worker.pong", {"job_id": ctx.get("job_id")})
    log.info("worker_ping", user_id=user_id, receivers=receivers)
    return "pong"
