"""arq worker entrypoint: `arq app.worker.settings.WorkerSettings`."""

from __future__ import annotations

from typing import Any, ClassVar

from arq.connections import RedisSettings
from arq.cron import CronJob

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.worker import jobs

_settings = get_settings()


async def startup(ctx: dict[str, Any]) -> None:
    configure_logging(_settings.LOG_LEVEL)
    ctx["settings"] = _settings


async def shutdown(ctx: dict[str, Any]) -> None:
    return None


class WorkerSettings:
    functions: ClassVar[list[Any]] = [jobs.ping]
    # Filled in later phases: expire_plans (5 min), fetch_news (1 h), pre_news_alerts (1 min),
    # weekly_coach (hourly, per-user timezone), balance_snapshot (daily) — see PLAN §5.2.
    cron_jobs: ClassVar[list[CronJob]] = []
    redis_settings = RedisSettings.from_dsn(_settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_tries = 3  # jobs raise `jobs.retry_with_backoff(ctx)` for exponential backoff
    job_timeout = 300
    keep_result = 3600
    retry_jobs = True
