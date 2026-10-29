"""Positions (F-07), execution ↔ plan matching (F-10) and the shared recalculation used by
manual entry and broker ingest (F-08)."""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.config import Settings
from app.core.effects import Effects
from app.core.errors import AppError, Conflict, NotFound
from app.modules.accounts import service as accounts
from app.modules.accounts.models import RiskProfileVersion, TradingAccount
from app.modules.audit.service import record
from app.modules.market_data import service as market_data
from app.modules.plans import service as plans
from app.modules.plans.models import TradePlan, TradePlanRevision
from app.modules.playbook.models import Setup
from app.modules.positions import calc as pcalc
from app.modules.positions import matching
from app.modules.positions.models import Execution, OrderModification, Position
from app.modules.positions.schemas import (
    Counts,
    ExecutionIn,
    ExecutionOut,
    ListFilters,
    ManualPositionIn,
    MatchCandidate,
    MatchQueueItem,
    ModificationOut,
    PlanRef,
    PositionCalcOut,
    PositionList,
    PositionOut,
    PositionSummary,
    UnplannedReason,
)
from app.modules.risk import service as risk
from app.modules.risk.calculator import ConversionRateRequired, value_per_price_unit
from app.modules.symbols.models import Symbol
from app.modules.users.models import User

MATCH_ENGINE_VERSION = 1
# Plans a trade can be linked to (drafts only via the manual picker — they make it unplanned).
MATCHABLE = plans.TRADE_DRIVEN
# Position + account name / currency + symbol code / digits + plan (outer join) + setup name.
SummarySelect = Select[Position, str, str, str, int, TradePlan, str]
REF_RE = re.compile(r"^#?t?-?(\d{1,9})$", re.IGNORECASE)


def utcnow() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ maths helpers


async def value_fn(
    session: AsyncSession, account: TradingAccount, symbol: Symbol, rate: Decimal | None
) -> pcalc.ValuePerUnit:
    """Money per 1.0 price move per lot, in the account currency (risk calculator rules)."""
    spec = await risk.symbol_spec(session, account, symbol)

    def per_unit(price: Decimal) -> Decimal:
        return value_per_price_unit(spec, account.currency, price, rate)

    try:
        per_unit(Decimal(1))  # fail early on a cross pair without a rate
    except ConversionRateRequired as exc:
        raise AppError(exc.code, str(exc), status_code=422, details=exc.details) from exc
    return per_unit


def fills_from_rows(rows: Iterable[Execution]) -> list[pcalc.Fill]:
    return [
        pcalc.Fill(
            side=e.side,  # type: ignore[arg-type]
            lot=e.lot,
            price=e.price,
            at=e.executed_at,
            commission=e.commission,
            swap=e.swap,
            profit=e.profit,
        )
        for e in rows
    ]


def _fills_from_input(rows: Sequence[ExecutionIn]) -> list[pcalc.Fill]:
    return [
        pcalc.Fill(
            side=e.side,
            lot=e.lot,
            price=e.price,
            at=e.executed_at.astimezone(UTC),
            commission=e.commission,
            swap=e.swap,
        )
        for e in rows
    ]


def apply_calc(position: Position, c: pcalc.PositionCalc) -> None:
    position.status = c.status
    position.opened_at, position.closed_at = c.opened_at, c.closed_at
    position.avg_entry, position.avg_exit = c.avg_entry, c.avg_exit
    position.total_lot, position.open_lot = c.total_lot, c.open_lot
    position.gross_pnl, position.commission, position.swap = c.gross_pnl, c.commission, c.swap
    position.net_pnl = c.net_pnl
    position.initial_risk_amount, position.r_multiple = c.initial_risk_amount, c.r_multiple


def _input_error(exc: pcalc.PositionInputError) -> AppError:
    return AppError(exc.code, str(exc), status_code=422, details=exc.details)


async def next_ref_no(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Running "#T-n" per trader. Locks the user row so concurrent imports don't collide."""
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    current = await session.scalar(
        select(func.coalesce(func.max(Position.ref_no), 0)).where(Position.user_id == user_id)
    )
    return int(current or 0) + 1


async def refresh_excursions(session: AsyncSession, position: Position) -> None:
    """MAE / MFE from stored bars while the position was open (closed trades only)."""
    if position.status != "closed" or position.closed_at is None:
        return
    rng = await market_data.price_range(
        session, position.symbol_id, position.opened_at, position.closed_at
    )
    if rng is None:
        return
    exc = pcalc.excursions(
        position.direction,  # type: ignore[arg-type]
        position.avg_entry,
        [rng.high],
        [rng.low],
    )
    if exc is not None:
        position.mae, position.mfe = exc.mae, exc.mfe


async def recalculate(
    session: AsyncSession, position: Position, account: TradingAccount, symbol: Symbol
) -> pcalc.PositionCalc:
    """Re-derive every number of a position from its stored executions."""
    rows = (
        (await session.execute(select(Execution).where(Execution.position_id == position.id)))
        .scalars()
        .all()
    )
    per_unit = await value_fn(session, account, symbol, position.quote_to_account_rate)
    result = pcalc.compute(
        position.direction,  # type: ignore[arg-type]
        fills_from_rows(rows),
        per_unit,
        initial_sl=position.initial_sl,
    )
    apply_calc(position, result)
    await refresh_excursions(session, position)
    return result


# ------------------------------------------------------------------ plan references


def _plan_ref(plan: TradePlan, setup_name: str) -> PlanRef:
    return PlanRef(
        id=plan.id,
        scenario_label=plan.scenario_label,
        setup_id=plan.setup_id,
        setup_name=setup_name,
        status=plan.status,
        entry_type=plan.entry_type,
        entry_price=plan.entry_price,
        stop_loss=plan.stop_loss,
        locked_at=plan.locked_at,
    )


def unplanned_reason(
    is_unplanned: bool, plan: TradePlan | None, opened_at: datetime
) -> UnplannedReason | None:
    if not is_unplanned:
        return None
    if plan is None:
        return "no_plan"
    if plan.locked_at is None:
        return "plan_not_locked"
    return "locked_after_entry" if plan.locked_at > opened_at else None


async def _values_at(
    session: AsyncSession, plan_rows: Sequence[TradePlan], at: datetime
) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """(entry, SL) of each plan as of `at`: the latest revision made by then (a revision after
    the entry must not move the target), else the current values."""
    out = {p.id: (p.entry_price, p.stop_loss) for p in plan_rows}
    if not plan_rows:
        return out
    stmt = (
        select(TradePlanRevision.plan_id, TradePlanRevision.snapshot)
        .where(
            TradePlanRevision.plan_id.in_([p.id for p in plan_rows]),
            TradePlanRevision.changed_at <= at,
        )
        .order_by(TradePlanRevision.plan_id, TradePlanRevision.revision_no.desc())
        .distinct(TradePlanRevision.plan_id)
    )
    for plan_id, snap in (await session.execute(stmt)).all():
        out[plan_id] = (Decimal(snap["entry_price"]), Decimal(snap["stop_loss"]))
    return out


async def _first_entry(session: AsyncSession, position_id: uuid.UUID) -> Decimal:
    price = await session.scalar(
        select(Execution.price)
        .where(Execution.position_id == position_id, Execution.side == "in")
        .order_by(Execution.executed_at, Execution.id)
        .limit(1)
    )
    if price is None:
        raise NotFound("Position has no entry")
    return Decimal(price)


async def _candidate_plans(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    symbol_id: uuid.UUID,
    direction: str,
    opened_at: datetime,
    tz: ZoneInfo,
    include_drafts: bool = False,
) -> list[tuple[TradePlan, str]]:
    """Same account / symbol / direction; locked in the time window, or planned for the entry
    day ±1 (so near misses can be shown and chosen by hand)."""
    day = opened_at.astimezone(tz).date()
    statuses = (*MATCHABLE, "draft") if include_drafts else MATCHABLE
    in_window = and_(
        TradePlan.locked_at.is_not(None),
        TradePlan.locked_at <= opened_at,
        or_(TradePlan.valid_until.is_(None), TradePlan.valid_until >= opened_at),
    )
    near_day = TradePlan.plan_date.between(day - timedelta(days=1), day + timedelta(days=1))
    stmt = (
        select(TradePlan, Setup.name)
        .join(Setup, Setup.id == TradePlan.setup_id)
        .where(
            TradePlan.user_id == user_id,
            TradePlan.account_id == account_id,
            TradePlan.symbol_id == symbol_id,
            TradePlan.direction == direction,
            TradePlan.status.in_(statuses),
            or_(in_window, near_day),
        )
        .order_by(TradePlan.locked_at.desc().nulls_last(), TradePlan.created_at.desc())
        .limit(20)
    )
    return [(p, name) for p, name in (await session.execute(stmt)).all()]


def _targets(
    rows: Sequence[tuple[TradePlan, str]], values: dict[uuid.UUID, tuple[Decimal, Decimal]]
) -> list[matching.PlanTarget]:
    return [
        matching.PlanTarget(
            plan_id=p.id,
            entry_price=values[p.id][0],
            stop_loss=values[p.id][1],
            locked_at=p.locked_at,
            valid_until=p.valid_until,
        )
        for p, _ in rows
    ]


def _candidates_out(
    rows: Sequence[tuple[TradePlan, str]], decision: matching.Decision
) -> list[MatchCandidate]:
    by_id = {p.id: (p, name) for p, name in rows}
    out = []
    for ev in decision.evaluations:
        plan, name = by_id[ev.plan_id]
        out.append(
            MatchCandidate(
                plan=_plan_ref(plan, name),
                distance=ev.distance,
                pct_of_sl=ev.pct_of_sl,
                within_price=ev.within_price,
                within_time=ev.within_time,
                eligible=ev.eligible,
                recommended=ev.plan_id == decision.recommended,
            )
        )
    return out


async def _decide(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    symbol_id: uuid.UUID,
    direction: str,
    opened_at: datetime,
    first_entry: Decimal,
    tolerance: Decimal,
    include_drafts: bool = False,
) -> tuple[list[tuple[TradePlan, str]], matching.Decision]:
    tz = await plans.user_zone(session, AccessContext(user_id=user_id))
    rows = await _candidate_plans(
        session,
        user_id=user_id,
        account_id=account_id,
        symbol_id=symbol_id,
        direction=direction,
        opened_at=opened_at,
        tz=tz,
        include_drafts=include_drafts,
    )
    values = await _values_at(session, [p for p, _ in rows], opened_at)
    return rows, matching.decide(_targets(rows, values), first_entry, opened_at, tolerance)


async def link(
    session: AsyncSession, position: Position, plan: TradePlan | None, match_status: str
) -> None:
    """Attach / detach a plan and keep both plans' statuses in step (F-10 AC3)."""
    old = position.plan_id
    position.plan_id = plan.id if plan else None
    position.match_status = match_status
    position.matched_at = utcnow() if match_status != "pending" else None
    position.is_unplanned = plan is None or matching.is_unplanned(
        plan.locked_at, position.opened_at
    )
    await session.flush()
    for plan_id in {old, position.plan_id} - {None}:
        assert plan_id is not None
        await plans.sync_with_positions(session, plan_id)


async def auto_match(
    session: AsyncSession, position: Position, first_entry: Decimal, tolerance: Decimal
) -> matching.Decision:
    """F-10 AC1-AC2: one eligible locked plan → linked; none / several → match queue."""
    rows, decision = await _decide(
        session,
        user_id=position.user_id,
        account_id=position.account_id,
        symbol_id=position.symbol_id,
        direction=position.direction,
        opened_at=position.opened_at,
        first_entry=first_entry,
        tolerance=tolerance,
    )
    position.match_meta = {
        "engine": MATCH_ENGINE_VERSION,
        "tolerance": str(tolerance),
        "fill": str(first_entry),
        "decision": decision.status,
        "recommended": str(decision.recommended) if decision.recommended else None,
        "evaluations": [
            {
                "plan_id": str(e.plan_id),
                "distance": str(e.distance),
                "pct_of_sl": str(e.pct_of_sl),
                "within_price": e.within_price,
                "within_time": e.within_time,
            }
            for e in decision.evaluations
        ],
    }
    chosen = next((p for p, _ in rows if p.id == decision.plan_id), None)
    await link(session, position, chosen, "auto" if chosen else "pending")
    return decision


# ------------------------------------------------------------------ events


def after_change(session: AsyncSession, fx: Effects, position: Position, event: str) -> None:
    """Realtime events + the Phase 6 recompute hook (adherence / quality after close or match)."""
    data = {
        "id": str(position.id),
        "status": position.status,
        "match_status": position.match_status,
    }
    fx.publish(session, position.user_id, event, data)
    if position.match_status == "pending":
        fx.publish(session, position.user_id, "match.pending", {"id": str(position.id)})
    if position.status == "closed":
        fx.enqueue(
            session, "recompute_position", str(position.id), job_id=f"recompute:{position.id}"
        )


# ------------------------------------------------------------------ manual entry


async def _owned_plan(
    session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID, body: ManualPositionIn
) -> TradePlan:
    plan = await get_owned_or_404(session, TradePlan, plan_id, ctx)
    if (plan.account_id, plan.symbol_id, plan.direction) != (
        body.account_id,
        body.symbol_id,
        body.direction,
    ):
        raise AppError(
            "plan_mismatch",
            "The plan is for another account, symbol or direction",
            status_code=422,
        )
    return plan


async def _prepare(
    session: AsyncSession, ctx: AccessContext, body: ManualPositionIn
) -> tuple[TradingAccount, Symbol, TradePlan | None, pcalc.PositionCalc]:
    account = await accounts.get_account(session, ctx, body.account_id)
    symbol = await session.get(Symbol, body.symbol_id)
    if symbol is None:
        raise NotFound("Symbol not found")
    plan = await _owned_plan(session, ctx, body.plan_id, body) if body.plan_id else None
    fills = _fills_from_input(body.executions)
    try:
        pcalc.validate(body.direction, fills, body.initial_sl)
        per_unit = await value_fn(session, account, symbol, body.quote_to_account_rate)
        result = pcalc.compute(body.direction, fills, per_unit, initial_sl=body.initial_sl)
    except pcalc.PositionInputError as exc:
        raise _input_error(exc) from exc
    return account, symbol, plan, result


async def preview(
    session: AsyncSession, ctx: AccessContext, body: ManualPositionIn
) -> PositionCalcOut:
    account, _, plan, c = await _prepare(session, ctx, body)
    reason: UnplannedReason | None = None
    if body.unplanned:
        reason = "no_plan"
    elif plan is not None:
        reason = unplanned_reason(
            matching.is_unplanned(plan.locked_at, c.opened_at), plan, c.opened_at
        )
    return PositionCalcOut(
        status=c.status,
        avg_entry=c.avg_entry,
        avg_exit=c.avg_exit,
        total_lot=c.total_lot,
        open_lot=c.open_lot,
        gross_pnl=c.gross_pnl,
        commission=c.commission,
        swap=c.swap,
        net_pnl=c.net_pnl,
        initial_risk_amount=c.initial_risk_amount,
        r_multiple=c.r_multiple,
        currency=account.currency,
        unplanned_reason=reason,
    )


async def create_manual(
    session: AsyncSession,
    ctx: AccessContext,
    fx: Effects,
    settings: Settings,
    body: ManualPositionIn,
) -> PositionOut:
    account, symbol, plan, c = await _prepare(session, ctx, body)
    if not account.is_active:
        raise Conflict("account_archived", "Unarchive the account to add trades to it")
    version = await accounts.risk_profile_at(session, account.id, c.opened_at)
    position = Position(
        user_id=ctx.owner_id,
        account_id=account.id,
        symbol_id=symbol.id,
        ref_no=await next_ref_no(session, ctx.owner_id),
        direction=body.direction,
        source="manual",
        initial_sl=body.initial_sl,
        initial_tp=body.initial_tp,
        current_sl=body.initial_sl,
        current_tp=body.initial_tp,
        quote_to_account_rate=body.quote_to_account_rate,
        risk_profile_version_id=version.id if version else None,
        match_meta={},
    )
    apply_calc(position, c)
    session.add(position)
    await session.flush()
    session.add_all(
        Execution(
            account_id=account.id,
            position_id=position.id,
            side=e.side,
            lot=e.lot,
            price=e.price,
            executed_at=e.executed_at.astimezone(UTC),
            commission=e.commission,
            swap=e.swap,
        )
        for e in body.executions
    )
    await session.flush()
    await refresh_excursions(session, position)
    if plan is not None:
        await link(session, position, plan, "manual")
    elif body.unplanned:
        await link(session, position, None, "manual")
    else:
        await auto_match(session, position, c.first_entry, settings.MATCH_TOLERANCE_SL)
    await record(
        session,
        ctx,
        action="create",
        entity="position",
        entity_id=position.id,
        after={
            "ref_no": position.ref_no,
            "source": "manual",
            "match_status": position.match_status,
        },
        account_id=account.id,
    )
    after_change(session, fx, position, "position.created")
    return await detail(session, ctx, position.id)


async def delete_position(
    session: AsyncSession, ctx: AccessContext, fx: Effects, position_id: uuid.UUID
) -> None:
    """Manual / OCR trades only — a synced trade would just come back with the next sync."""
    position = await get_owned_or_404(session, Position, position_id, ctx)
    if position.source not in ("manual", "ocr"):
        raise Conflict("position_synced", "Trades synced from the broker cannot be deleted")
    plan_id = position.plan_id
    await session.delete(position)
    await session.flush()
    if plan_id:
        await plans.sync_with_positions(session, plan_id)
    await record(
        session,
        ctx,
        action="delete",
        entity="position",
        entity_id=position_id,
        before={"ref_no": position.ref_no, "source": position.source},
        account_id=position.account_id,
    )
    fx.publish(session, ctx.owner_id, "position.deleted", {"id": str(position_id)})


# ------------------------------------------------------------------ matching API


async def _position_with_entry(
    session: AsyncSession, ctx: AccessContext, position_id: uuid.UUID
) -> tuple[Position, Decimal]:
    position = await get_owned_or_404(session, Position, position_id, ctx)
    return position, await _first_entry(session, position.id)


async def match_candidates(
    session: AsyncSession, ctx: AccessContext, settings: Settings, position_id: uuid.UUID
) -> list[MatchCandidate]:
    position, first = await _position_with_entry(session, ctx, position_id)
    rows, decision = await _decide(
        session,
        user_id=position.user_id,
        account_id=position.account_id,
        symbol_id=position.symbol_id,
        direction=position.direction,
        opened_at=position.opened_at,
        first_entry=first,
        tolerance=settings.MATCH_TOLERANCE_SL,
    )
    return _candidates_out(rows, decision)


async def plan_options(
    session: AsyncSession,
    ctx: AccessContext,
    settings: Settings,
    *,
    account_id: uuid.UUID,
    symbol_id: uuid.UUID,
    direction: str,
    opened_at: datetime,
    entry_price: Decimal,
) -> list[MatchCandidate]:
    """Plans for the manual-entry picker, drafts included (they make the trade unplanned)."""
    await accounts.get_account(session, ctx, account_id)
    rows, decision = await _decide(
        session,
        user_id=ctx.owner_id,
        account_id=account_id,
        symbol_id=symbol_id,
        direction=direction,
        opened_at=opened_at.astimezone(UTC),
        first_entry=entry_price,
        tolerance=settings.MATCH_TOLERANCE_SL,
        include_drafts=True,
    )
    return _candidates_out(rows, decision)


async def set_match(
    session: AsyncSession,
    ctx: AccessContext,
    fx: Effects,
    position_id: uuid.UUID,
    plan_id: uuid.UUID | None,
) -> PositionOut:
    """F-10 AC3: the trader picks the plan (or unplanned); metrics are recomputed."""
    position = await get_owned_or_404(session, Position, position_id, ctx)
    plan: TradePlan | None = None
    if plan_id is not None:
        plan = await get_owned_or_404(session, TradePlan, plan_id, ctx)
        if (plan.account_id, plan.symbol_id, plan.direction) != (
            position.account_id,
            position.symbol_id,
            position.direction,
        ):
            raise AppError(
                "plan_mismatch",
                "The plan is for another account, symbol or direction",
                status_code=422,
            )
    before = {"plan_id": str(position.plan_id) if position.plan_id else None}
    await link(session, position, plan, "manual")
    await record(
        session,
        ctx,
        action="match",
        entity="position",
        entity_id=position.id,
        before=before,
        after={"plan_id": str(plan_id) if plan_id else None, "is_unplanned": position.is_unplanned},
        account_id=position.account_id,
    )
    after_change(session, fx, position, "position.updated")
    # Re-matching changes the plan comparison even for an open trade.
    fx.enqueue(session, "recompute_position", str(position.id), job_id=f"recompute:{position.id}")
    return await detail(session, ctx, position.id)


async def match_queue(
    session: AsyncSession, ctx: AccessContext, settings: Settings, account_id: uuid.UUID | None
) -> list[MatchQueueItem]:
    stmt = _summary_query(ctx).where(Position.match_status == "pending")
    if account_id is not None:
        stmt = stmt.where(Position.account_id == account_id)
    rows = (await session.execute(stmt.order_by(Position.opened_at, Position.id).limit(50))).all()
    items = []
    for row in rows:
        summary = _summary(row)
        first = await _first_entry(session, summary.id)
        plan_rows, decision = await _decide(
            session,
            user_id=ctx.owner_id,
            account_id=summary.account_id,
            symbol_id=summary.symbol_id,
            direction=summary.direction,
            opened_at=summary.opened_at,
            first_entry=first,
            tolerance=settings.MATCH_TOLERANCE_SL,
        )
        items.append(
            MatchQueueItem(
                position=summary,
                first_entry=first,
                candidates=_candidates_out(plan_rows, decision),
            )
        )
    return items


# ------------------------------------------------------------------ read


def _summary_query(ctx: AccessContext) -> SummarySelect:
    stmt: SummarySelect = (
        select(
            Position,
            TradingAccount.name,
            TradingAccount.currency,
            Symbol.code,
            Symbol.digits,
            TradePlan,
            Setup.name,
        )
        .join(TradingAccount, TradingAccount.id == Position.account_id)
        .join(Symbol, Symbol.id == Position.symbol_id)
        .outerjoin(TradePlan, TradePlan.id == Position.plan_id)
        .outerjoin(Setup, Setup.id == TradePlan.setup_id)
        .where(Position.user_id == ctx.owner_id)
    )
    return stmt


def _summary(row: Any) -> PositionSummary:
    p: Position = row[0]
    plan: TradePlan | None = row[5]
    return PositionSummary(
        id=p.id,
        ref_no=p.ref_no,
        account_id=p.account_id,
        account_name=row[1],
        currency=row[2],
        symbol_id=p.symbol_id,
        symbol_code=row[3],
        digits=row[4],
        direction=p.direction,
        source=p.source,
        status=p.status,
        opened_at=p.opened_at,
        closed_at=p.closed_at,
        avg_entry=p.avg_entry,
        avg_exit=p.avg_exit,
        total_lot=p.total_lot,
        open_lot=p.open_lot,
        net_pnl=p.net_pnl,
        r_multiple=p.r_multiple,
        current_sl=p.current_sl,
        current_tp=p.current_tp,
        is_unplanned=p.is_unplanned,
        match_status=p.match_status,
        plan=_plan_ref(plan, row[6]) if plan is not None else None,
        # Every closed trade waits for its review until the review form exists (F-12 AC1, Phase 5).
        review_status="pending" if p.status == "closed" else None,
    )


TAB_WHERE = {
    "all": None,
    "review": Position.status == "closed",
    "pending": Position.match_status == "pending",
    "unplanned": and_(Position.is_unplanned.is_(True), Position.match_status != "pending"),
    "open": Position.status == "open",
}


def _day_start(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)


async def _filtered(session: AsyncSession, ctx: AccessContext, f: ListFilters) -> SummarySelect:
    stmt = _summary_query(ctx)
    if f.account_id:
        stmt = stmt.where(Position.account_id == f.account_id)
    if f.symbol_id:
        stmt = stmt.where(Position.symbol_id == f.symbol_id)
    if f.setup_id:
        stmt = stmt.where(TradePlan.setup_id == f.setup_id)
    if f.direction:
        stmt = stmt.where(Position.direction == f.direction)
    if f.date_from or f.date_to:
        tz = await plans.user_zone(session, ctx)
        if f.date_from:
            stmt = stmt.where(Position.opened_at >= _day_start(f.date_from, tz))
        if f.date_to:
            stmt = stmt.where(Position.opened_at < _day_start(f.date_to + timedelta(days=1), tz))
    q = f.q.strip()
    if q:
        ref = REF_RE.match(q)
        like = f"%{q}%"
        conds: list[ColumnElement[bool]] = [
            Symbol.code.ilike(like),
            Position.broker_symbol.ilike(like),
            Setup.name.ilike(like),
        ]
        if ref:
            conds.append(Position.ref_no == int(ref.group(1)))
        stmt = stmt.where(or_(*conds))
    return stmt


async def list_positions(
    session: AsyncSession, ctx: AccessContext, f: ListFilters, *, offset: int, limit: int
) -> PositionList:
    base = await _filtered(session, ctx, f)
    sub = base.with_only_columns(
        Position.status, Position.match_status, Position.is_unplanned
    ).subquery()
    counts_row = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(sub.c.status == "closed"),
                func.count().filter(sub.c.match_status == "pending"),
                func.count().filter(
                    and_(sub.c.is_unplanned.is_(True), sub.c.match_status != "pending")
                ),
                func.count().filter(sub.c.status == "open"),
            ).select_from(sub)
        )
    ).one()
    counts = Counts(
        all=counts_row[0],
        review=counts_row[1],
        pending=counts_row[2],
        unplanned=counts_row[3],
        open=counts_row[4],
    )
    where = TAB_WHERE[f.tab]
    stmt = base.where(where) if where is not None else base
    rows = (
        await session.execute(
            stmt.order_by(Position.opened_at.desc(), Position.id.desc()).offset(offset).limit(limit)
        )
    ).all()
    return PositionList(
        items=[_summary(r) for r in rows],
        total=getattr(counts, f.tab),
        offset=offset,
        limit=limit,
        counts=counts,
    )


def _r_of(distance: Decimal | None, p: Position) -> Decimal | None:
    if distance is None or p.initial_sl is None:
        return None
    risk = abs(p.avg_entry - p.initial_sl)
    return (distance / risk).quantize(Decimal("0.01")) if risk else None


async def detail(session: AsyncSession, ctx: AccessContext, position_id: uuid.UUID) -> PositionOut:
    row = (
        await session.execute(_summary_query(ctx).where(Position.id == position_id))
    ).one_or_none()
    if row is None:
        raise NotFound()
    p: Position = row[0]
    plan: TradePlan | None = row[5]
    executions = (
        (
            await session.execute(
                select(Execution)
                .where(Execution.position_id == p.id)
                .order_by(Execution.executed_at, Execution.side, Execution.id)
            )
        )
        .scalars()
        .all()
    )
    mods = (
        (
            await session.execute(
                select(OrderModification)
                .where(OrderModification.position_id == p.id)
                .order_by(OrderModification.modified_at, OrderModification.id)
            )
        )
        .scalars()
        .all()
    )
    version = (
        await session.scalar(
            select(RiskProfileVersion.version).where(
                RiskProfileVersion.id == p.risk_profile_version_id
            )
        )
        if p.risk_profile_version_id
        else None
    )
    return PositionOut(
        **_summary(row).model_dump(),
        broker_position_id=p.broker_position_id,
        broker_symbol=p.broker_symbol,
        initial_sl=p.initial_sl,
        initial_tp=p.initial_tp,
        gross_pnl=p.gross_pnl,
        commission=p.commission,
        swap=p.swap,
        initial_risk_amount=p.initial_risk_amount,
        mae=p.mae,
        mfe=p.mfe,
        mae_r=_r_of(p.mae, p),
        mfe_r=_r_of(p.mfe, p),
        unplanned_reason=unplanned_reason(p.is_unplanned, plan, p.opened_at),
        matched_at=p.matched_at,
        match_meta=p.match_meta or {},
        risk_profile_version=version,
        executions=[ExecutionOut.model_validate(e) for e in executions],
        modifications=[ModificationOut.model_validate(m) for m in mods],
    )


EXPORT_LIMIT = 10_000
CSV_COLUMNS = (
    "ref_no",
    "account",
    "symbol",
    "direction",
    "source",
    "status",
    "opened_at",
    "closed_at",
    "lot",
    "avg_entry",
    "avg_exit",
    "net_pnl",
    "currency",
    "r_multiple",
    "plan",
    "setup",
    "match_status",
    "unplanned",
)


async def export_csv(session: AsyncSession, ctx: AccessContext, f: ListFilters) -> str:
    base = await _filtered(session, ctx, f)
    where = TAB_WHERE[f.tab]
    stmt = base.where(where) if where is not None else base
    rows = (
        await session.execute(
            stmt.order_by(Position.opened_at.desc(), Position.id.desc()).limit(EXPORT_LIMIT)
        )
    ).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        s = _summary(row)
        writer.writerow(
            [
                f"T-{s.ref_no}",
                s.account_name,
                s.symbol_code,
                s.direction.upper(),
                s.source,
                s.status,
                s.opened_at.isoformat(),
                s.closed_at.isoformat() if s.closed_at else "",
                s.total_lot,
                s.avg_entry,
                s.avg_exit if s.avg_exit is not None else "",
                s.net_pnl,
                s.currency,
                s.r_multiple if s.r_multiple is not None else "",
                s.plan.scenario_label if s.plan else "",
                s.plan.setup_name if s.plan else "",
                s.match_status,
                "yes" if s.is_unplanned else "no",
            ]
        )
    return buf.getvalue()


# ------------------------------------------------------------------ today / counts


async def pending_match_count(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID | None
) -> int:
    stmt = select(func.count()).where(
        Position.user_id == ctx.owner_id, Position.match_status == "pending"
    )
    if account_id:
        stmt = stmt.where(Position.account_id == account_id)
    return int(await session.scalar(stmt) or 0)


async def pending_review_count(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID | None
) -> int:
    stmt = select(func.count()).where(Position.user_id == ctx.owner_id, Position.status == "closed")
    if account_id:
        stmt = stmt.where(Position.account_id == account_id)
    return int(await session.scalar(stmt) or 0)


async def closed_between(
    session: AsyncSession,
    ctx: AccessContext,
    start: datetime,
    end: datetime,
    account_id: uuid.UUID | None,
) -> list[tuple[str, Decimal, Decimal, int]]:
    """(currency, net P/L, sum R, trades) of trades closed in [start, end)."""
    stmt = (
        select(
            TradingAccount.currency,
            func.coalesce(func.sum(Position.net_pnl), 0),
            func.coalesce(func.sum(Position.r_multiple), 0),
            func.count(),
        )
        .join(TradingAccount, TradingAccount.id == Position.account_id)
        .where(
            Position.user_id == ctx.owner_id,
            Position.status == "closed",
            Position.closed_at >= start,
            Position.closed_at < end,
        )
        .group_by(TradingAccount.currency)
    )
    if account_id:
        stmt = stmt.where(Position.account_id == account_id)
    return [
        (cur, Decimal(net or 0), Decimal(r or 0), int(n))
        for cur, net, r, n in (await session.execute(stmt))
    ]
