"""arq job functions. Each receives arq's `ctx` (contains `redis`) first."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from arq import Retry

from app.core.db import commit_and_flush_hooks
from app.core.effects import Effects
from app.core.pubsub import publish
from app.modules.connections.ctrader import sync as ctrader_sync
from app.modules.connections.ctrader.client import CTraderError, websocket_connect
from app.modules.connections.models import BrokerConnection
from app.modules.plans import service as plans_service
from app.modules.positions.models import Position

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


async def expire_plans(ctx: dict[str, Any]) -> int:
    """Cron (every 5 min): plans past `valid_until` without a trade → expired (F-06 AC6)."""
    sessionmaker = ctx["sessionmaker"]
    async with sessionmaker() as session, session.begin():
        expired = await plans_service.expire_due(session)
    if expired:
        log.info("plans_expired", count=expired)
    return expired


async def recompute_position(ctx: dict[str, Any], position_id: str) -> str:
    """Hook fired when a position closes or its plan link changes (PLAN §5.2 recompute pipeline).

    Phase 6 plugs the adherence -> deviations -> quality -> quadrant engine in here; for now it
    only tells the trader's open pages that the trade's metrics may have changed."""
    sessionmaker = ctx["sessionmaker"]
    async with sessionmaker() as session:
        position = await session.get(Position, uuid.UUID(position_id))
    if position is None:
        return "gone"
    await publish(ctx["redis"], position.user_id, "metrics.updated", {"position_id": position_id})
    return "ok"


CTRADER_MAX_TRIES = 3


async def sync_ctrader(ctx: dict[str, Any], connection_id: str, full_history: bool = False) -> str:
    """cTrader history / incremental sync (F-08 AC2, AC4). Network trouble → retry with backoff
    up to 3 tries; an invalid token can't be retried — the trader must reconnect (design 24)."""
    sessionmaker = ctx["sessionmaker"]
    settings = ctx["settings"]
    fx = Effects.from_worker(ctx)
    attempt = int(ctx.get("job_try", 1))
    try:
        async with sessionmaker() as session:
            conn = await session.get(
                BrokerConnection, uuid.UUID(connection_id), with_for_update=True
            )
            if conn is None or conn.kind != "ctrader_oauth":
                return "gone"
            result = await ctrader_sync.sync_connection(
                session,
                fx,
                settings,
                conn,
                full_history=full_history,
                connector=ctx.get("ctrader_connector", websocket_connect),
            )
            await commit_and_flush_hooks(session)
            log.info("ctrader_synced", connection_id=connection_id, deals=result.deals)
            return "ok"
    except (CTraderError, OSError, TimeoutError) as exc:
        auth_problem = isinstance(exc, CTraderError) and exc.is_auth
        if not auth_problem and attempt < CTRADER_MAX_TRIES:
            raise retry_with_backoff(ctx) from exc
        async with sessionmaker() as session:
            conn = await session.get(BrokerConnection, uuid.UUID(connection_id))
            if conn is not None:
                await ctrader_sync.record_failure(session, conn, exc, attempt, CTRADER_MAX_TRIES)
                account_user = await _account_user(session, conn.account_id)
                await session.commit()
                if account_user is not None:
                    await publish(
                        ctx["redis"],
                        account_user,
                        "sync.status",
                        {"connection_id": connection_id, "status": "error"},
                    )
        log.warning("ctrader_sync_failed", connection_id=connection_id, error=str(exc))
        return "error"


async def _account_user(session: Any, account_id: uuid.UUID) -> uuid.UUID | None:
    from app.modules.accounts.models import TradingAccount

    account = await session.get(TradingAccount, account_id)
    return account.user_id if account else None
