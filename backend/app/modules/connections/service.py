"""Broker connections of an account (F-08 AC1, AC6): MT5 API key, status, history, sync now."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings
from app.core.effects import Effects
from app.core.errors import AppError, Conflict, NotFound, Unauthorized
from app.modules.accounts import service as accounts
from app.modules.accounts.models import TradingAccount
from app.modules.audit.service import record
from app.modules.connections import keys
from app.modules.connections.models import BrokerConnection, IngestCommand, IngestionJob
from app.modules.connections.schemas import ConnectionOut, ConnectionStats, ConnectionStatus
from app.modules.plans import service as plans
from app.modules.positions.models import Execution, OrderModification


def utcnow() -> datetime:
    return datetime.now(UTC)


def status_of(conn: BrokerConnection, settings: Settings, now: datetime) -> ConnectionStatus:
    if conn.status == "error":
        return "error"
    if conn.kind == "mt5_ea":
        if conn.last_seen_at is None:
            return "pending"  # key made, EA not heard from yet
        fresh = now - conn.last_seen_at <= timedelta(seconds=settings.MT5_STALE_SEC)
        return "connected" if fresh else "offline"
    return "connected" if conn.status == "connected" else "pending"


async def _stats(
    session: AsyncSession, ctx: AccessContext, conn: BrokerConnection
) -> ConnectionStats:
    tz = await plans.user_zone(session, ctx)
    start = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz).astimezone(UTC)
    deals = await session.scalar(
        select(func.count()).where(
            Execution.account_id == conn.account_id,
            Execution.broker_deal_id.is_not(None),
            Execution.executed_at >= start,
        )
    )
    mods = await session.scalar(
        select(func.count()).where(
            OrderModification.account_id == conn.account_id,
            OrderModification.modified_at >= start,
        )
    )
    since = (conn.external_meta or {}).get("history_from")
    days = None
    if since is not None and conn.history_synced_at is not None:
        days = max(0, round((conn.history_synced_at.timestamp() - int(since)) / 86400))
    return ConnectionStats(
        deals_today=int(deals or 0), mods_today=int(mods or 0), history_days=days
    )


async def to_out(
    session: AsyncSession, ctx: AccessContext, settings: Settings, conn: BrokerConnection
) -> ConnectionOut:
    meta = conn.external_meta or {}
    return ConnectionOut(
        id=conn.id,
        account_id=conn.account_id,
        kind=conn.kind,
        status=status_of(conn, settings, utcnow()),
        key_hint=keys.hint(conn.key_prefix, conn.key_last4),
        external_account_id=conn.external_account_id,
        server=meta.get("server"),
        ea_version=meta.get("ea_version"),
        last_seen_at=conn.last_seen_at,
        last_sync_at=conn.last_sync_at,
        last_error=conn.last_error,
        last_error_at=conn.last_error_at,
        history_synced_at=conn.history_synced_at,
        stats=await _stats(session, ctx, conn),
        created_at=conn.created_at,
    )


async def list_connections(
    session: AsyncSession, ctx: AccessContext, settings: Settings, account_id: uuid.UUID
) -> list[ConnectionOut]:
    await accounts.get_account(session, ctx, account_id)
    rows = (
        (
            await session.execute(
                select(BrokerConnection)
                .where(BrokerConnection.account_id == account_id)
                .order_by(BrokerConnection.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [await to_out(session, ctx, settings, c) for c in rows]


async def get_connection(
    session: AsyncSession, ctx: AccessContext, connection_id: uuid.UUID
) -> BrokerConnection:
    """Owner check through the account (404 for anyone else, F-01 AC4)."""
    stmt = (
        select(BrokerConnection)
        .join(TradingAccount, TradingAccount.id == BrokerConnection.account_id)
        .where(BrokerConnection.id == connection_id, TradingAccount.user_id == ctx.owner_id)
    )
    conn = (await session.execute(stmt)).scalar_one_or_none()
    if conn is None:
        raise NotFound()
    return conn


async def create_mt5_key(
    session: AsyncSession, ctx: AccessContext, settings: Settings, account_id: uuid.UUID
) -> tuple[BrokerConnection, str]:
    """New key for the account's EA; calling again rotates it (the old key stops at once)."""
    account = await accounts.get_account(session, ctx, account_id)
    if account.platform != "mt5":
        raise AppError("platform_mismatch", "MT5 keys are for MT5 accounts", status_code=422)
    conn = (
        await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.account_id == account_id, BrokerConnection.kind == "mt5_ea"
            )
        )
    ).scalar_one_or_none()
    rotated = conn is not None
    if conn is None:
        conn = BrokerConnection(
            account_id=account_id, kind="mt5_ea", status="pending", external_meta={}
        )
        session.add(conn)
    key = keys.new_key()
    conn.api_key_hash = keys.hash_key(key)
    conn.key_prefix, conn.key_last4 = key[: keys.HINT_PREFIX_LEN], key[-4:]
    await session.flush()
    await record(
        session,
        ctx,
        action="rotate_key" if rotated else "create",
        entity="broker_connection",
        entity_id=conn.id,
        after={"kind": "mt5_ea", "key_hint": keys.hint(conn.key_prefix, conn.key_last4)},
        account_id=account_id,
    )
    return conn, key


async def disconnect(session: AsyncSession, ctx: AccessContext, connection_id: uuid.UUID) -> None:
    """Remove the link (key / tokens). Imported trades stay."""
    conn = await get_connection(session, ctx, connection_id)
    await session.delete(conn)
    await session.flush()
    await record(
        session,
        ctx,
        action="delete",
        entity="broker_connection",
        entity_id=connection_id,
        before={"kind": conn.kind},
        account_id=conn.account_id,
    )


async def request_sync(
    session: AsyncSession, ctx: AccessContext, fx: Effects, connection_id: uuid.UUID
) -> BrokerConnection:
    """ "Sync ตอนนี้": MT5 → a resync command for the EA's next heartbeat (PLAN M14);
    cTrader → the sync job right away."""
    conn = await get_connection(session, ctx, connection_id)
    if conn.kind == "mt5_ea":
        exists = await session.scalar(
            select(func.count()).where(
                IngestCommand.connection_id == conn.id,
                IngestCommand.kind == "resync",
                IngestCommand.status == "pending",
            )
        )
        if not exists:
            session.add(
                IngestCommand(
                    connection_id=conn.id,
                    kind="resync",
                    params={"days": 7},
                    available_at=utcnow(),
                )
            )
    else:
        if conn.oauth_tokens is None:
            raise Conflict("not_connected", "Connect cTrader first")
        fx.enqueue(session, "sync_ctrader", str(conn.id), False, job_id=f"ctrader:{conn.id}")
    await session.flush()
    return conn


async def list_jobs(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, limit: int
) -> Sequence[IngestionJob]:
    await accounts.get_account(session, ctx, account_id)
    stmt = (
        select(IngestionJob)
        .where(IngestionJob.account_id == account_id)
        .order_by(IngestionJob.started_at.desc(), IngestionJob.id.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()


async def authenticate_key(session: AsyncSession, api_key: str | None) -> BrokerConnection:
    if not keys.looks_like_key(api_key):
        raise Unauthorized("invalid_api_key", "Missing or invalid API key")
    assert api_key is not None
    stmt = (
        select(BrokerConnection)
        .join(TradingAccount, TradingAccount.id == BrokerConnection.account_id)
        .where(
            BrokerConnection.api_key_hash == keys.hash_key(api_key),
            BrokerConnection.kind == "mt5_ea",
            TradingAccount.is_active.is_(True),
        )
        .with_for_update(of=BrokerConnection)
    )
    conn = (await session.execute(stmt)).scalar_one_or_none()
    if conn is None:
        raise Unauthorized("invalid_api_key", "Missing or invalid API key")
    return conn


async def save_ctrader_tokens(
    session: AsyncSession,
    ctx: AccessContext,
    account_id: uuid.UUID,
    sealed_tokens: str,
    expires_at: datetime,
) -> BrokerConnection:
    """After the OAuth consent: (re)link the account. The sync job picks the cTrader account."""
    await accounts.get_account(session, ctx, account_id)
    conn = (
        await session.execute(
            select(BrokerConnection).where(
                BrokerConnection.account_id == account_id,
                BrokerConnection.kind == "ctrader_oauth",
            )
        )
    ).scalar_one_or_none()
    relinked = conn is not None
    if conn is None:
        conn = BrokerConnection(account_id=account_id, kind="ctrader_oauth", external_meta={})
        session.add(conn)
    conn.oauth_tokens, conn.token_expires_at = sealed_tokens, expires_at
    conn.status, conn.last_error, conn.last_error_at = "pending", None, None
    await session.flush()
    await record(
        session,
        ctx,
        action="relink" if relinked else "create",
        entity="broker_connection",
        entity_id=conn.id,
        after={"kind": "ctrader_oauth"},
        account_id=account_id,
    )
    return conn
