"""One idempotent pipeline for broker data (F-08): MT5 EA batches and cTrader syncs.

deal → execution (unique per account + ticket, AC3) → position (unique per account + broker
position id) → recalculated → matched to a plan when new (F-10) → events. SL/TP changes become
`order_modifications` with the direction of risk; bars go to `ohlc_bars` (AC5) and fill MAE/MFE.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.effects import Effects
from app.modules.accounts import service as accounts
from app.modules.accounts.models import AccountSymbolOverride, TradingAccount
from app.modules.connections.models import BrokerConnection, IngestCommand, IngestionJob
from app.modules.connections.schemas import (
    CommandOut,
    Counted,
    DealIn,
    IngestIn,
    IngestOut,
    SymbolIn,
)
from app.modules.market_data import service as market_data
from app.modules.market_data.service import TF_SECONDS, BarIn
from app.modules.plans import service as plans
from app.modules.positions import calc as pcalc
from app.modules.positions import service as positions
from app.modules.positions.models import Execution, OrderModification, Position
from app.modules.symbols.models import Symbol

log = structlog.get_logger(__name__)

PLATFORM_OF = {"mt5_ea": "mt5", "ctrader_oauth": "ctrader"}
# OHLC around imported history only for recent trades — 90 days x 7 timeframes is a lot of bars.
HISTORY_OHLC_DAYS = 7
OHLC_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")


def _utc(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


def _opt(value: Decimal) -> Decimal | None:
    """Broker "0" means "not set"."""
    return value if value and value > 0 else None


@dataclass
class _Run:
    conn: BrokerConnection
    account: TradingAccount
    platform: str
    now: datetime
    accepted: Counted = field(default_factory=Counted)
    duplicates: Counted = field(default_factory=Counted)
    unknown: set[str] = field(default_factory=set)
    orphans: int = 0
    warnings: list[str] = field(default_factory=list)
    symbols: dict[str, Symbol | None] = field(default_factory=dict)
    positions: dict[str, Position] = field(default_factory=dict)
    created: set[uuid.UUID] = field(default_factory=set)
    touched: set[uuid.UUID] = field(default_factory=set)
    status_before: dict[uuid.UUID, str] = field(default_factory=dict)


async def _symbol(session: AsyncSession, run: _Run, name: str) -> Symbol | None:
    key = name.upper()
    if key not in run.symbols:
        found = await accounts.resolve_broker_symbol(session, run.account.id, name)
        run.symbols[key] = found[0] if found else None
        if found is None:
            run.unknown.add(name)
    return run.symbols[key]


async def _learn_symbol_specs(session: AsyncSession, run: _Run, specs: list[SymbolIn]) -> None:
    """Keep the broker's contract size / tick value per broker symbol (PLAN R9) so the risk
    calculator matches MT5. MT5 tick value is per `tick_size`; we store it per point."""
    for spec in specs:
        symbol = await _symbol(session, run, spec.name)
        if symbol is None:
            continue
        tick_value: Decimal | None = None
        if spec.tick_value and spec.tick_size and spec.tick_size > 0:
            point = spec.point or symbol.point_size
            tick_value = (spec.tick_value * point / spec.tick_size).quantize(Decimal("0.000001"))
        row = (
            await session.execute(
                select(AccountSymbolOverride).where(
                    AccountSymbolOverride.account_id == run.account.id,
                    func.upper(AccountSymbolOverride.broker_symbol) == spec.name.upper(),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = AccountSymbolOverride(
                account_id=run.account.id, symbol_id=symbol.id, broker_symbol=spec.name
            )
            session.add(row)
        if spec.contract_size and spec.contract_size > 0:
            row.contract_size = spec.contract_size
        if tick_value:
            row.tick_value = tick_value
    await session.flush()


async def _position_for(
    session: AsyncSession, run: _Run, deal: DealIn, symbol: Symbol
) -> Position | None:
    key = deal.position_id
    if key in run.positions:
        return run.positions[key]
    position = (
        await session.execute(
            select(Position).where(
                Position.account_id == run.account.id, Position.broker_position_id == key
            )
        )
    ).scalar_one_or_none()
    if position is None:
        if deal.entry != "in":
            return None  # the entry is older than the imported window
        long_ = deal.type == "buy"
        position = Position(
            user_id=run.account.user_id,
            account_id=run.account.id,
            symbol_id=symbol.id,
            ref_no=await positions.next_ref_no(session, run.account.user_id),
            direction="long" if long_ else "short",
            source=run.platform,
            broker_position_id=key,
            broker_symbol=deal.symbol,
            opened_at=_utc(deal.time),
            avg_entry=deal.price,
            total_lot=deal.volume,
            open_lot=deal.volume,
            initial_sl=_opt(deal.sl),
            initial_tp=_opt(deal.tp),
            current_sl=_opt(deal.sl),
            current_tp=_opt(deal.tp),
            match_meta={},
        )
        try:
            async with session.begin_nested():
                session.add(position)
                await session.flush()
        except IntegrityError:
            # A concurrent request created it first (same broker position id).
            position = (
                await session.execute(
                    select(Position).where(
                        Position.account_id == run.account.id, Position.broker_position_id == key
                    )
                )
            ).scalar_one()
        else:
            run.created.add(position.id)
    run.positions[key] = position
    run.status_before.setdefault(position.id, position.status)
    return position


async def _deals(session: AsyncSession, run: _Run, deals: list[DealIn]) -> None:
    for deal in sorted(deals, key=lambda d: (d.time, d.entry != "in", d.ticket)):
        symbol = await _symbol(session, run, deal.symbol)
        if symbol is None:
            continue
        position = await _position_for(session, run, deal, symbol)
        if position is None:
            run.orphans += 1
            continue
        if deal.entry == "inout":
            run.warnings.append(f"netting reversal {deal.ticket} recorded as an exit")
        side = "in" if deal.entry == "in" else "out"
        stmt = (
            insert(Execution)
            .values(
                id=uuid.uuid4(),
                account_id=run.account.id,
                position_id=position.id,
                broker_deal_id=deal.ticket,
                side=side,
                lot=deal.volume,
                price=deal.price,
                executed_at=_utc(deal.time),
                commission=deal.commission + deal.fee,
                swap=deal.swap,
                profit=deal.profit if side == "out" else None,
            )
            .on_conflict_do_nothing(index_elements=["account_id", "broker_deal_id"])
            .returning(Execution.id)
        )
        if (await session.execute(stmt)).first() is None:
            run.duplicates.deals += 1
            continue
        run.accepted.deals += 1
        run.touched.add(position.id)
        # A deal carries the SL/TP in force when it happened.
        if side == "in" and position.initial_sl is None and _opt(deal.sl):
            position.initial_sl = deal.sl
        if side == "in" and position.initial_tp is None and _opt(deal.tp):
            position.initial_tp = deal.tp


async def _modifications(session: AsyncSession, run: _Run, batch: IngestIn) -> None:
    for mod in sorted(batch.modifications, key=lambda m: (m.time, m.id)):
        position = (
            run.positions.get(mod.position_id)
            or (
                await session.execute(
                    select(Position).where(
                        Position.account_id == run.account.id,
                        Position.broker_position_id == mod.position_id,
                    )
                )
            ).scalar_one_or_none()
        )
        if position is None:
            run.orphans += 1
            continue
        old, new = _opt(mod.old), _opt(mod.new)
        stmt = (
            insert(OrderModification)
            .values(
                id=uuid.uuid4(),
                account_id=run.account.id,
                position_id=position.id,
                broker_event_id=mod.id,
                field=mod.field,
                old_value=old,
                new_value=new,
                modified_at=_utc(mod.time),
                direction_of_risk=pcalc.risk_direction(
                    position.direction,  # type: ignore[arg-type]
                    mod.field,
                    old,
                    new,
                ),
            )
            .on_conflict_do_nothing(index_elements=["account_id", "broker_event_id"])
            .returning(OrderModification.id)
        )
        if (await session.execute(stmt)).first() is None:
            run.duplicates.modifications += 1
            continue
        run.accepted.modifications += 1
        if mod.field == "sl":
            position.current_sl = new
            if position.initial_sl is None and old is None and new is not None:
                position.initial_sl = new  # first stop set right after the entry
                run.touched.add(position.id)  # R needs a recompute
        else:
            position.current_tp = new
        run.positions.setdefault(mod.position_id, position)
        run.status_before.setdefault(position.id, position.status)


async def _open_snapshot(session: AsyncSession, run: _Run, batch: IngestIn) -> None:
    """Current SL/TP of every open position (heartbeat)."""
    ids = [p.position_id for p in batch.positions]
    if not ids:
        return
    rows = (
        await session.execute(
            select(Position).where(
                Position.account_id == run.account.id,
                Position.broker_position_id.in_(ids),
                Position.status == "open",
            )
        )
    ).scalars()
    by_id = {p.broker_position_id: p for p in rows}
    for snap in batch.positions:
        position = by_id.get(snap.position_id)
        if position is not None:
            position.current_sl, position.current_tp = _opt(snap.sl), _opt(snap.tp)


async def _bars(session: AsyncSession, run: _Run, batch: IngestIn) -> None:
    for series in batch.ohlc:
        symbol = await _symbol(session, run, series.symbol)
        if symbol is None or not series.bars:
            continue
        bars = [
            BarIn(ts=_utc(t), open=o, high=h, low=lo, close=c, volume=v)
            for t, o, h, lo, c, v in series.bars
        ]
        new = await market_data.upsert_bars(
            session,
            symbol_id=symbol.id,
            timeframe=series.timeframe,
            bars=bars,
            source_account_id=run.account.id,
        )
        run.accepted.bars += new
        run.duplicates.bars += len(bars) - new
        # Fill MAE/MFE of closed trades these bars cover.
        first, last = min(b.ts for b in bars), max(b.ts for b in bars)
        waiting = (
            await session.execute(
                select(Position).where(
                    Position.account_id == run.account.id,
                    Position.symbol_id == symbol.id,
                    Position.status == "closed",
                    Position.mae.is_(None),
                    Position.opened_at >= first,
                    Position.opened_at <= last,
                )
            )
        ).scalars()
        for position in waiting:
            await positions.refresh_excursions(session, position)


def _ohlc_commands(run: _Run, position: Position, settings: Settings) -> list[IngestCommand]:
    """Ask the EA for bars around a closed trade (F-08 AC5): now, and once more after the
    bars following the exit exist (capped at a day)."""
    if run.conn.kind != "mt5_ea" or position.closed_at is None or not position.broker_symbol:
        return []
    out: list[IngestCommand] = []
    n = settings.OHLC_BARS_AROUND
    for tf in OHLC_TIMEFRAMES:
        step = TF_SECONDS[tf]
        start = int(position.opened_at.timestamp()) - n * step
        end = int(position.closed_at.timestamp()) + n * step
        params = {"symbol": position.broker_symbol, "from": start, "to": end, "timeframes": [tf]}
        later = position.closed_at + timedelta(seconds=min(n * step, 86400))
        for available in (run.now, later):
            out.append(
                IngestCommand(
                    connection_id=run.conn.id, kind="ohlc", params=params, available_at=available
                )
            )
    return out


async def _finish_positions(
    session: AsyncSession, run: _Run, fx: Effects, settings: Settings, history: bool
) -> None:
    by_id = {p.id: p for p in run.positions.values()}
    symbols = {s.id: s for s in run.symbols.values() if s is not None}
    for position_id in run.touched:
        position = by_id[position_id]
        symbol = symbols.get(position.symbol_id) or await session.get(Symbol, position.symbol_id)
        assert symbol is not None
        try:
            result = await positions.recalculate(session, position, run.account, symbol)
        except pcalc.PositionInputError as exc:
            run.warnings.append(f"position {position.broker_position_id}: {exc}")
            continue
        new = position_id in run.created
        if new:
            version = await accounts.risk_profile_at(session, run.account.id, position.opened_at)
            position.risk_profile_version_id = version.id if version else None
            decision = await positions.auto_match(
                session, position, result.first_entry, settings.MATCH_TOLERANCE_SL
            )
            # An imported old trade with no plan around at all is plainly unplanned — don't
            # flood the match queue with the whole 90-day history.
            if history and decision.status == "pending" and not decision.evaluations:
                await positions.link(session, position, None, "auto")
        just_closed = run.status_before.get(position_id) == "open" and position.status == "closed"
        if (new or just_closed) and position.status == "closed":
            if position.plan_id:
                await plans.sync_with_positions(session, position.plan_id)
            recent = position.closed_at and position.closed_at > run.now - timedelta(
                days=HISTORY_OHLC_DAYS
            )
            if not history or recent:
                session.add_all(_ohlc_commands(run, position, settings))
        positions.after_change(
            session, fx, position, "position.created" if new else "position.updated"
        )
    await session.flush()


async def _deliver_commands(session: AsyncSession, run: _Run) -> list[CommandOut]:
    rows = (
        (
            await session.execute(
                select(IngestCommand)
                .where(
                    IngestCommand.connection_id == run.conn.id,
                    IngestCommand.status == "pending",
                    IngestCommand.available_at <= run.now,
                )
                .order_by(IngestCommand.available_at, IngestCommand.id)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    for cmd in rows:
        cmd.status, cmd.delivered_at = "delivered", run.now
    return [CommandOut(id=c.id, kind=c.kind, params=c.params) for c in rows]


async def apply(
    session: AsyncSession,
    fx: Effects,
    settings: Settings,
    conn: BrokerConnection,
    batch: IngestIn,
    *,
    job_kind: str | None = None,
) -> IngestOut:
    account = await session.get(TradingAccount, conn.account_id, with_for_update=True)
    assert account is not None
    now = datetime.now(UTC)
    run = _Run(conn=conn, account=account, platform=PLATFORM_OF[conn.kind], now=now)
    status_before = conn.status

    # Account heartbeat (PLAN M26).
    a = batch.account
    if a.balance is not None:
        account.last_balance = a.balance
        account.last_equity = a.equity if a.equity is not None else a.balance
        account.last_equity_at = now
    if a.login:
        conn.external_account_id = a.login
    meta = dict(conn.external_meta or {})
    meta.update(
        {
            k: v
            for k, v in {
                "server": a.server,
                "company": a.company,
                "currency": a.currency,
                "margin_mode": a.margin_mode,
                "ea_version": batch.ea_version,
                "is_live": a.is_live,
            }.items()
            if v not in ("", None)
        }
    )
    conn.last_seen_at = now

    await _learn_symbol_specs(session, run, batch.symbols)
    await _deals(session, run, batch.deals)
    await _modifications(session, run, batch)
    await _open_snapshot(session, run, batch)
    await _bars(session, run, batch)
    history = batch.history is not None
    await _finish_positions(session, run, fx, settings, history)

    got_data = run.accepted.deals or run.accepted.modifications or run.accepted.bars
    if got_data:
        conn.last_sync_at = now
    if run.accepted.deals and not meta.get("first_deal_at"):
        meta["first_deal_at"] = now.isoformat()
        fx.publish(session, account.user_id, "sync.first_deal", {"connection_id": str(conn.id)})
    if batch.history is not None:
        meta.setdefault("history_from", batch.history.from_)
        meta["history_from"] = min(int(meta["history_from"]), batch.history.from_)
        if batch.history.final:
            conn.history_synced_at = now
    conn.external_meta = meta

    if run.unknown:
        conn.last_error = "unknown_symbols: " + ", ".join(sorted(run.unknown))[:450]
        conn.last_error_at = now
    elif conn.status == "error" or got_data:
        conn.last_error = None
    conn.status = "connected"

    if batch.deals or batch.modifications or history or job_kind:
        kind = job_kind or ("history" if history else "sync")
        session.add(
            IngestionJob(
                account_id=account.id,
                connection_id=conn.id,
                kind=kind,
                source=run.platform,
                status="warning" if (run.unknown or run.warnings) else "success",
                stats={
                    "deals": run.accepted.deals,
                    "duplicates": run.duplicates.deals,
                    "modifications": run.accepted.modifications,
                    "positions": len(run.touched),
                    "new_positions": len(run.created),
                    "bars": run.accepted.bars,
                    "orphans": run.orphans,
                    "unknown_symbols": sorted(run.unknown),
                    "warnings": run.warnings[:20],
                },
                error=conn.last_error if run.unknown else None,
                started_at=now,
                finished_at=datetime.now(UTC),
            )
        )
    commands = await _deliver_commands(session, run) if conn.kind == "mt5_ea" else []
    await session.flush()
    if status_before != "connected" or got_data:
        fx.publish(
            session,
            account.user_id,
            "sync.status",
            {"connection_id": str(conn.id), "account_id": str(account.id), "status": "connected"},
        )
    if run.warnings:
        log.info("ingest_warnings", connection_id=str(conn.id), warnings=run.warnings[:5])
    return IngestOut(
        accepted=run.accepted,
        duplicates=run.duplicates,
        unknown_symbols=sorted(run.unknown),
        server_time=int(now.timestamp()),
        commands=commands,
    )
