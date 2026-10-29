"""cTrader sync (F-08 AC2, AC4, AC5): history import, incremental sync, OHLC, live events."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.crypto import SecretBox
from app.core.effects import Effects
from app.modules.accounts.models import TradingAccount
from app.modules.connections import ingest
from app.modules.connections.ctrader import mapper, oauth
from app.modules.connections.ctrader import protocol as p
from app.modules.connections.ctrader.client import (
    Connector,
    CTraderClient,
    CTraderError,
    websocket_connect,
)
from app.modules.connections.models import BrokerConnection, IngestionJob
from app.modules.connections.schemas import AccountIn, DealIn, OpenPositionIn
from app.modules.positions.models import Position

log = structlog.get_logger(__name__)

CHUNK = 500  # deals per ingest batch (same as the EA)
OHLC_RECENT_DAYS = 7
OHLC_MAX_POSITIONS = 20
OHLC_TIMEFRAMES = ("M1", "M5", "M15", "H1", "H4", "D1")
TRENDBAR_PAUSE_S = 0.25  # historical requests are rate limited (≈5/s)
REFRESH_BEFORE = timedelta(days=1)


def ws_url(settings: Settings, is_live: bool) -> str:
    return settings.CTRADER_WS_LIVE if is_live else settings.CTRADER_WS_DEMO


@dataclass
class SyncResult:
    deals: int = 0
    duplicates: int = 0
    positions: int = 0
    bars: int = 0
    unknown_symbols: list[str] = field(default_factory=list)


async def fresh_tokens(
    session: AsyncSession, settings: Settings, conn: BrokerConnection, http: httpx.AsyncClient
) -> oauth.Tokens:
    """Stored tokens, refreshed a day before they expire (and re-sealed)."""
    box = SecretBox(settings.FERNET_KEY)
    if conn.oauth_tokens is None:
        raise CTraderError("NOT_CONNECTED", "no tokens")
    tokens = oauth.Tokens.unsealed(box, conn.oauth_tokens)
    if tokens.expires_at - datetime.now(UTC) < REFRESH_BEFORE:
        tokens = await oauth.refresh(settings, http, tokens.refresh_token)
        conn.oauth_tokens, conn.token_expires_at = tokens.sealed(box), tokens.expires_at
        await session.flush()
    return tokens


async def _pick_account(
    client: CTraderClient, conn: BrokerConnection, account: TradingAccount, token: str
) -> tuple[int, bool]:
    """ctidTraderAccountId of this TrackTrade account: matched by login number, or the only one."""
    meta = conn.external_meta or {}
    if conn.external_account_id and "ctid" in meta:
        return int(meta["ctid"]), bool(meta.get("is_live", True))
    accounts = await client.accounts(token)
    wanted = (account.account_number or "").lstrip("#").strip()
    match = [a for a in accounts if str(a.get("traderLogin", "")) == wanted] if wanted else []
    if not match and len(accounts) == 1:
        match = accounts
    if not match:
        raise CTraderError(
            "ACCOUNT_NOT_FOUND",
            "Set the account number to the cTrader login you want to link",
        )
    chosen = match[0]
    conn.external_account_id = str(chosen.get("traderLogin", chosen["ctidTraderAccountId"]))
    conn.external_meta = {
        **meta,
        "ctid": int(chosen["ctidTraderAccountId"]),
        "is_live": bool(chosen.get("isLive", True)),
    }
    return int(chosen["ctidTraderAccountId"]), bool(chosen.get("isLive", True))


async def open_session(
    settings: Settings,
    conn: BrokerConnection,
    account: TradingAccount,
    tokens: oauth.Tokens,
    connector: Connector,
) -> tuple[CTraderClient, int]:
    """Connected + app/account authorised client on the right (live / demo) host."""
    meta = conn.external_meta or {}
    is_live = bool(meta.get("is_live", True))
    client = await CTraderClient.open(ws_url(settings, is_live), connector)
    try:
        await client.app_auth(settings.CTRADER_CLIENT_ID, settings.CTRADER_CLIENT_SECRET)
        ctid, live = await _pick_account(client, conn, account, tokens.access_token)
        if live != is_live:  # account list came from the other host
            await client.close()
            client = await CTraderClient.open(ws_url(settings, live), connector)
            await client.app_auth(settings.CTRADER_CLIENT_ID, settings.CTRADER_CLIENT_SECRET)
        await client.account_auth(ctid, tokens.access_token)
    except BaseException:
        await client.close()
        raise
    return client, ctid


def _chunks(items: Sequence[DealIn], size: int) -> list[Sequence[DealIn]]:
    return [items[i : i + size] for i in range(0, len(items), size)] or [[]]


async def sync_connection(
    session: AsyncSession,
    fx: Effects,
    settings: Settings,
    conn: BrokerConnection,
    *,
    full_history: bool,
    connector: Connector = websocket_connect,
    http: httpx.AsyncClient | None = None,
) -> SyncResult:
    account = await session.get(TradingAccount, conn.account_id)
    assert account is not None
    own_http = http is None
    http = http or httpx.AsyncClient()
    try:
        tokens = await fresh_tokens(session, settings, conn, http)
    finally:
        if own_http:
            await http.aclose()
    client, ctid = await open_session(settings, conn, account, tokens, connector)
    result = SyncResult()
    try:
        now = datetime.now(UTC)
        history = full_history or conn.history_synced_at is None
        if history:
            since = now - timedelta(days=settings.CTRADER_HISTORY_DAYS)
        else:
            since = (conn.last_sync_at or now - timedelta(days=7)) - timedelta(hours=1)
        raw_deals = await client.deals(
            ctid, int(since.timestamp() * 1000), int(now.timestamp() * 1000)
        )
        raw_positions = await client.reconcile(ctid)
        symbol_ids = {int(d["symbolId"]) for d in raw_deals} | {
            int(x["tradeData"]["symbolId"]) for x in raw_positions if "tradeData" in x
        }
        symbols = await client.symbols(ctid, symbol_ids)
        trader = await client.trader(ctid)
        acc_in = mapper.trader_account(
            trader,
            login=conn.external_account_id or str(ctid),
            is_live=(conn.external_meta or {}).get("is_live"),
        )
        deals = [d for d in (mapper.deal(x, symbols) for x in raw_deals) if d is not None]
        opens = [o for o in (mapper.position(x, symbols) for x in raw_positions) if o is not None]
        chunks = _chunks(deals, CHUNK)
        start_s, end_s = int(since.timestamp()), int(now.timestamp())
        for i, chunk in enumerate(chunks):
            last = i == len(chunks) - 1
            out = await ingest.apply(
                session,
                fx,
                settings,
                conn,
                mapper.batch(
                    acc_in,
                    symbols=list(symbols.values()) if i == 0 else (),
                    deals=chunk,
                    positions=opens if last else (),
                    history=(start_s, end_s, last) if history else None,
                ),
                job_kind="history" if history else "sync",
            )
            result.deals += out.accepted.deals
            result.duplicates += out.duplicates.deals
            result.unknown_symbols += out.unknown_symbols
        result.positions = len({d.position_id for d in deals})
        result.bars = await _sync_ohlc(session, fx, settings, conn, client, ctid, symbols, acc_in)
        # Live position snapshot for the stream's SL/TP diffing.
        meta = dict(conn.external_meta or {})
        meta["open_positions"] = {o.position_id: o.model_dump(mode="json") for o in opens}
        conn.external_meta = meta
        conn.status, conn.last_error, conn.last_sync_at = "connected", None, now
        await session.flush()
    finally:
        await client.close()
    return result


async def _sync_ohlc(
    session: AsyncSession,
    fx: Effects,
    settings: Settings,
    conn: BrokerConnection,
    client: CTraderClient,
    ctid: int,
    symbols: dict[int, mapper.SymbolInfo],
    acc_in: Any,
) -> int:
    """Trendbars ±N around recently closed trades that have no MAE/MFE yet (F-08 AC5)."""
    import asyncio

    by_name = {s.name.upper(): s for s in symbols.values()}
    since = datetime.now(UTC) - timedelta(days=OHLC_RECENT_DAYS)
    rows = (
        (
            await session.execute(
                select(Position)
                .where(
                    Position.account_id == conn.account_id,
                    Position.status == "closed",
                    Position.mae.is_(None),
                    Position.closed_at >= since,
                )
                .order_by(Position.closed_at.desc())
                .limit(OHLC_MAX_POSITIONS)
            )
        )
        .scalars()
        .all()
    )
    total = 0
    n = settings.OHLC_BARS_AROUND
    from app.modules.market_data.service import TF_SECONDS

    for pos in rows:
        sym = by_name.get((pos.broker_symbol or "").upper())
        if sym is None or pos.closed_at is None:
            continue
        series = []
        for tf in OHLC_TIMEFRAMES:
            step = TF_SECONDS[tf] * 1000
            start = int(pos.opened_at.timestamp() * 1000) - n * step
            end = min(
                int(pos.closed_at.timestamp() * 1000) + n * step,
                int(datetime.now(UTC).timestamp() * 1000),
            )
            raw = await client.trendbars(ctid, sym.symbol_id, tf, start, end)
            if raw:
                series.append(mapper.trendbars(raw, tf, sym))
            await asyncio.sleep(TRENDBAR_PAUSE_S)
        if series:
            out = await ingest.apply(session, fx, settings, conn, mapper.batch(acc_in, ohlc=series))
            total += out.accepted.bars
    return total


async def record_failure(
    session: AsyncSession, conn: BrokerConnection, exc: Exception, attempt: int, max_tries: int
) -> None:
    """Connection → error + a failed history entry ("401 invalid_grant · retry 3/3 ล้มเหลว")."""
    now = datetime.now(UTC)
    code = exc.code if isinstance(exc, CTraderError) else type(exc).__name__
    conn.status = "error"
    conn.last_error = (
        str(exc)[:450] if not isinstance(exc, CTraderError) else f"{code}: {exc.message}"[:450]
    )
    conn.last_error_at = now
    session.add(
        IngestionJob(
            account_id=conn.account_id,
            connection_id=conn.id,
            kind="sync",
            source="ctrader",
            status="error",
            stats={"code": code, "auth": isinstance(exc, CTraderError) and exc.is_auth},
            error=conn.last_error,
            attempts=attempt,
            started_at=now,
            finished_at=now,
        )
    )
    await session.flush()


# ------------------------------------------------------------------ live stream events


async def handle_event(
    session: AsyncSession,
    fx: Effects,
    settings: Settings,
    conn: BrokerConnection,
    msg: dict[str, Any],
    symbols: dict[int, mapper.SymbolInfo],
    login: str,
) -> bool:
    """One pushed execution event → ingest (deal and / or SL/TP change). Returns True if used."""
    if msg.get("payloadType") != p.EXECUTION_EVENT:
        return False
    body = msg.get("payload", {})
    deals: list[DealIn] = []
    mods = []
    opens: list[OpenPositionIn] = []
    if body.get("deal"):
        d = mapper.deal(body["deal"], symbols)
        if d is not None:
            deals.append(d)
    if body.get("position"):
        after = mapper.position(body["position"], symbols)
        if after is not None:
            meta = dict(conn.external_meta or {})
            known = meta.get("open_positions", {})
            before_raw = known.get(after.position_id)
            before = OpenPositionIn.model_validate(before_raw) if before_raw else None
            at_ms = int(
                body["position"].get("utcLastUpdateTimestamp")
                or datetime.now(UTC).timestamp() * 1000
            )
            mods = mapper.modifications(before, after, at_ms)
            known[after.position_id] = after.model_dump(mode="json")
            meta["open_positions"] = known
            conn.external_meta = meta
            opens.append(after)
    if not (deals or mods or opens):
        return False
    acc_in = AccountIn(login=login)
    await ingest.apply(
        session,
        fx,
        settings,
        conn,
        mapper.batch(acc_in, deals=deals, positions=opens, mods=mods),
    )
    return True
