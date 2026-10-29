"""Real-time cTrader events (F-08 AC2): `python -m app.modules.connections.ctrader.stream`.

One long-lived WebSocket per linked account. Every minute the set of linked accounts is
re-read; a dropped socket reconnects with backoff (1 s → 60 s). An invalid token marks the
connection as error and stops that account until the trader reconnects it.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

import httpx
import structlog
from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import commit_and_flush_hooks, create_engine, create_sessionmaker
from app.core.effects import Effects
from app.core.logging import configure_logging
from app.modules.accounts.models import TradingAccount
from app.modules.connections.ctrader import protocol as p
from app.modules.connections.ctrader import sync
from app.modules.connections.ctrader.client import Connector, CTraderError, websocket_connect
from app.modules.connections.models import BrokerConnection

log = structlog.get_logger(__name__)
RESCAN_S = 60
MAX_BACKOFF_S = 60


async def _connections(sm: async_sessionmaker[AsyncSession]) -> set[uuid.UUID]:
    async with sm() as session:
        rows = await session.execute(
            select(BrokerConnection.id).where(
                BrokerConnection.kind == "ctrader_oauth",
                BrokerConnection.oauth_tokens.is_not(None),
                BrokerConnection.status != "error",
                BrokerConnection.external_account_id.is_not(None),  # first sync done
            )
        )
        return {r[0] for r in rows}


async def follow(
    connection_id: uuid.UUID,
    sm: async_sessionmaker[AsyncSession],
    fx: Effects,
    settings: Settings,
    connector: Connector = websocket_connect,
) -> None:
    """Keep one account's stream open until cancelled or its token is rejected."""
    backoff = 1.0
    while True:
        try:
            async with sm() as session:
                conn = await session.get(BrokerConnection, connection_id)
                if conn is None or conn.status == "error":
                    return
                account = await session.get(TradingAccount, conn.account_id)
                assert account is not None
                async with httpx.AsyncClient() as http:
                    tokens = await sync.fresh_tokens(session, settings, conn, http)
                await session.commit()
                client, ctid = await sync.open_session(settings, conn, account, tokens, connector)
            try:
                async with sm() as session:
                    conn = await session.get(BrokerConnection, connection_id)
                    assert conn is not None
                    ids = {int(x["tradeData"]["symbolId"]) for x in await client.reconcile(ctid)}
                    symbols = await client.symbols(ctid, ids) if ids else {}
                    login = conn.external_account_id or str(ctid)
                    await session.commit()
                backoff = 1.0
                log.info("ctrader_stream_open", connection_id=str(connection_id))
                while not client.closed.is_set():
                    msg: dict[str, Any] = await client.events.get()
                    kind = msg.get("payloadType")
                    if kind == p.ACCOUNTS_TOKEN_INVALIDATED_EVENT:
                        raise CTraderError("CH_ACCESS_TOKEN_INVALID", "token invalidated")
                    if kind == p.CLIENT_DISCONNECT_EVENT:
                        break
                    body = msg.get("payload", {})
                    sid = (body.get("deal") or body.get("position", {}).get("tradeData") or {}).get(
                        "symbolId"
                    )
                    if sid is not None and int(sid) not in symbols:
                        symbols.update(await client.symbols(ctid, {int(sid)}))
                    async with sm() as session:
                        conn = await session.get(
                            BrokerConnection, connection_id, with_for_update=True
                        )
                        if conn is None:
                            return
                        if await sync.handle_event(
                            session, fx, settings, conn, msg, symbols, login
                        ):
                            await commit_and_flush_hooks(session)
            finally:
                await client.close()
        except asyncio.CancelledError:
            raise
        except CTraderError as exc:
            if exc.is_auth:
                async with sm() as session:
                    conn = await session.get(BrokerConnection, connection_id)
                    if conn is not None:
                        await sync.record_failure(session, conn, exc, 1, 1)
                        await session.commit()
                log.warning("ctrader_stream_auth_failed", connection_id=str(connection_id))
                return
            log.warning("ctrader_stream_error", connection_id=str(connection_id), error=str(exc))
        except Exception:
            log.exception("ctrader_stream_crashed", connection_id=str(connection_id))
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF_S)


async def main() -> None:  # pragma: no cover — process entrypoint
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    if not (settings.CTRADER_CLIENT_ID and settings.FERNET_KEY):
        log.warning("ctrader_stream_disabled", reason="CTRADER_CLIENT_ID / FERNET_KEY not set")
        await asyncio.Event().wait()  # stay up so the container is healthy; nothing to stream
    engine = create_engine(settings.DATABASE_URL)
    sm = create_sessionmaker(engine)
    queue = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    fx = Effects(redis=queue, queue=queue)
    tasks: dict[uuid.UUID, asyncio.Task[None]] = {}
    try:
        while True:
            wanted = await _connections(sm)
            for cid in wanted - tasks.keys():
                tasks[cid] = asyncio.create_task(follow(cid, sm, fx, settings))
            for cid in list(tasks):
                if cid not in wanted or tasks[cid].done():
                    tasks.pop(cid).cancel()
            await asyncio.sleep(RESCAN_S)
    finally:
        for task in tasks.values():
            task.cancel()
        with contextlib.suppress(Exception):
            await asyncio.gather(*tasks.values(), return_exceptions=True)
        await queue.aclose()
        await engine.dispose()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
