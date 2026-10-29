"""Market analysis (F-05), chart drawings (F-19 AC3), OHLC (broker bars, else a mock)."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import AppError, Conflict, NotFound
from app.modules.accounts import service as accounts
from app.modules.analysis.models import ChartDrawing, MarketAnalysis
from app.modules.analysis.schemas import (
    AnalysisCreate,
    AnalysisOut,
    AnalysisSummary,
    AnalysisUpdate,
    Bar,
    DrawingOut,
    DrawingsPut,
    KeyLevelOut,
    OhlcOut,
    narrative_text,
)
from app.modules.audit.service import record, snapshot
from app.modules.market_data import service as market_data
from app.modules.plans import service as plans
from app.modules.plans.models import TradePlan
from app.modules.symbols.models import Symbol

# ------------------------------------------------------------------ analyses


async def _get(session: AsyncSession, ctx: AccessContext, analysis_id: uuid.UUID) -> MarketAnalysis:
    return await get_owned_or_404(session, MarketAnalysis, analysis_id, ctx)


async def _symbol(session: AsyncSession, symbol_id: uuid.UUID) -> Symbol:
    symbol = await session.get(Symbol, symbol_id)
    if symbol is None:
        raise NotFound("Symbol not found")
    return symbol


def _levels(raw: list[dict[str, Any]]) -> list[KeyLevelOut]:
    return [
        KeyLevelOut(
            price=Decimal(str(lv["price"])),
            price_to=Decimal(str(lv["price_to"])) if lv.get("price_to") is not None else None,
            kind=lv.get("kind", "other"),
            label=lv.get("label", ""),
        )
        for lv in raw or []
    ]


def _summary(a: MarketAnalysis, code: str, plan_count: int) -> AnalysisSummary:
    return AnalysisSummary(
        id=a.id,
        account_id=a.account_id,
        symbol_id=a.symbol_id,
        symbol_code=code,
        analysis_date=a.analysis_date,
        htf_bias=a.htf_bias,
        key_levels=_levels(a.key_levels),
        timeframes=list(a.timeframes or []),
        session=a.session,
        confidence=a.confidence,
        narrative_text=a.narrative_text[:600],
        plan_count=plan_count,
        updated_at=a.updated_at,
    )


async def list_analyses(
    session: AsyncSession,
    ctx: AccessContext,
    *,
    on: date | None = None,
    symbol_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[AnalysisSummary]:
    n_plans = (
        select(func.count())
        .where(TradePlan.analysis_id == MarketAnalysis.id)
        .correlate(MarketAnalysis)
        .scalar_subquery()
    )
    stmt = (
        select(MarketAnalysis, Symbol.code, n_plans)
        .join(Symbol, Symbol.id == MarketAnalysis.symbol_id)
        .where(MarketAnalysis.user_id == ctx.owner_id)
    )
    if on is not None:
        stmt = stmt.where(MarketAnalysis.analysis_date == on)
    if symbol_id is not None:
        stmt = stmt.where(MarketAnalysis.symbol_id == symbol_id)
    if account_id is not None:
        # An analysis without an account applies to every account.
        stmt = stmt.where(
            (MarketAnalysis.account_id == account_id) | MarketAnalysis.account_id.is_(None)
        )
    stmt = stmt.order_by(MarketAnalysis.analysis_date.desc(), MarketAnalysis.updated_at.desc())
    rows = (await session.execute(stmt.limit(limit))).all()
    return [_summary(a, code, int(n)) for a, code, n in rows]


async def detail(session: AsyncSession, ctx: AccessContext, analysis_id: uuid.UUID) -> AnalysisOut:
    a = await _get(session, ctx, analysis_id)
    symbol = await _symbol(session, a.symbol_id)
    briefs = await plans.briefs(session, ctx, analysis_id=a.id)
    return AnalysisOut(
        **_summary(a, symbol.code, len(briefs)).model_dump(),
        narrative=a.narrative or {"type": "doc", "content": []},
        created_at=a.created_at,
        plans=sorted(briefs, key=lambda p: p.scenario_label),
    )


async def create(session: AsyncSession, ctx: AccessContext, body: AnalysisCreate) -> AnalysisOut:
    if body.account_id is not None:
        await accounts.get_account(session, ctx, body.account_id)
    await _symbol(session, body.symbol_id)
    day = body.analysis_date or plans.local_today(await plans.user_zone(session, ctx))
    a = MarketAnalysis(
        user_id=ctx.owner_id,
        account_id=body.account_id,
        symbol_id=body.symbol_id,
        analysis_date=day,
        htf_bias=body.htf_bias,
        key_levels=[lv.model_dump(mode="json") for lv in body.key_levels],
        timeframes=list(body.timeframes),
        session=body.session,
        narrative=body.narrative,
        narrative_text=narrative_text(body.narrative),
        confidence=body.confidence,
    )
    session.add(a)
    await session.flush()
    await session.refresh(a)
    await record(
        session,
        ctx,
        action="create",
        entity="market_analysis",
        entity_id=a.id,
        after=snapshot(a),
        account_id=a.account_id,
    )
    return await detail(session, ctx, a.id)


async def update(
    session: AsyncSession, ctx: AccessContext, analysis_id: uuid.UUID, body: AnalysisUpdate
) -> AnalysisOut:
    a = await _get(session, ctx, analysis_id)
    before = snapshot(a)
    data = body.model_dump(exclude_unset=True)
    if "account_id" in data:
        if body.account_id is not None:
            await accounts.get_account(session, ctx, body.account_id)
        a.account_id = body.account_id
    if body.symbol_id is not None and body.symbol_id != a.symbol_id:
        has_plans = await session.scalar(select(func.count()).where(TradePlan.analysis_id == a.id))
        if has_plans:
            raise Conflict(
                "analysis_has_plans", "Plans use this analysis; its symbol cannot change"
            )
        await _symbol(session, body.symbol_id)
        a.symbol_id = body.symbol_id
    if body.analysis_date is not None:
        a.analysis_date = body.analysis_date
    if body.htf_bias is not None:
        a.htf_bias = body.htf_bias
    if body.key_levels is not None:
        a.key_levels = [lv.model_dump(mode="json") for lv in body.key_levels]
    if body.timeframes is not None:
        a.timeframes = list(body.timeframes)
    if "session" in data:
        a.session = body.session
    if body.narrative is not None:
        a.narrative = body.narrative
        a.narrative_text = narrative_text(body.narrative)
    if body.confidence is not None:
        a.confidence = body.confidence
    await session.flush()
    await session.refresh(a)
    after = snapshot(a)
    if after != before:
        await record(
            session,
            ctx,
            action="update",
            entity="market_analysis",
            entity_id=a.id,
            before=before,
            after=after,
            account_id=a.account_id,
        )
    return await detail(session, ctx, a.id)


async def delete_analysis(
    session: AsyncSession, ctx: AccessContext, analysis_id: uuid.UUID
) -> None:
    a = await _get(session, ctx, analysis_id)
    if await session.scalar(select(func.count()).where(TradePlan.analysis_id == a.id)):
        raise Conflict("analysis_has_plans", "Plans use this analysis; it cannot be deleted")
    before = snapshot(a)
    await session.execute(
        delete(ChartDrawing).where(
            ChartDrawing.owner_type == "analysis", ChartDrawing.owner_id == a.id
        )
    )
    await session.delete(a)
    await session.flush()
    await record(
        session,
        ctx,
        action="delete",
        entity="market_analysis",
        entity_id=analysis_id,
        before=before,
    )


# ------------------------------------------------------------------ chart drawings


async def _owner_symbol(
    session: AsyncSession, ctx: AccessContext, owner_type: str, owner_id: uuid.UUID
) -> uuid.UUID:
    if owner_type == "analysis":
        return (await _get(session, ctx, owner_id)).symbol_id
    if owner_type == "plan":
        return (await get_owned_or_404(session, TradePlan, owner_id, ctx)).symbol_id
    raise AppError("unsupported_owner", "Drawings belong to an analysis or a plan", status_code=422)


def _drawing_out(d: ChartDrawing) -> DrawingOut:
    payload = d.payload or {}
    return DrawingOut.model_validate(
        {
            "id": d.id,
            "tool": d.tool,
            "timeframe": d.timeframe,
            "points": payload.get("points", []),
            "style": payload.get("style", {}),
            "text": payload.get("text", ""),
        }
    )


async def list_drawings(
    session: AsyncSession, ctx: AccessContext, owner_type: str, owner_id: uuid.UUID
) -> list[DrawingOut]:
    await _owner_symbol(session, ctx, owner_type, owner_id)
    stmt = (
        select(ChartDrawing)
        .where(
            ChartDrawing.user_id == ctx.owner_id,
            ChartDrawing.owner_type == owner_type,
            ChartDrawing.owner_id == owner_id,
        )
        .order_by(ChartDrawing.created_at)
    )
    return [_drawing_out(d) for d in (await session.execute(stmt)).scalars()]


async def put_drawings(
    session: AsyncSession,
    ctx: AccessContext,
    owner_type: str,
    owner_id: uuid.UUID,
    body: DrawingsPut,
) -> list[DrawingOut]:
    """Replace the owner's drawings with `body` (the editor saves its whole state)."""
    symbol_id = await _owner_symbol(session, ctx, owner_type, owner_id)
    await session.execute(
        delete(ChartDrawing).where(
            ChartDrawing.user_id == ctx.owner_id,
            ChartDrawing.owner_type == owner_type,
            ChartDrawing.owner_id == owner_id,
        )
    )
    await session.flush()
    seen: set[uuid.UUID] = set()
    for d in body.drawings:
        drawing_id = d.id if d.id is not None and d.id not in seen else uuid.uuid4()
        seen.add(drawing_id)
        session.add(
            ChartDrawing(
                id=drawing_id,
                user_id=ctx.owner_id,
                owner_type=owner_type,
                owner_id=owner_id,
                symbol_id=symbol_id,
                timeframe=d.timeframe,
                tool=d.tool,
                payload={
                    "points": [p.model_dump(mode="json") for p in d.points],
                    "style": d.style.model_dump(),
                    "text": d.text,
                },
            )
        )
    await session.flush()
    return await list_drawings(session, ctx, owner_type, owner_id)


# ------------------------------------------------------------------ mock OHLC

TF_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600,
    "H4": 14400,
    "D1": 86400,
    "W1": 604800,
}
# Rough levels so an empty account still shows a plausible chart.
DEFAULT_PRICE = {
    "XAUUSD": "4380",
    "XAGUSD": "52",
    "EURUSD": "1.0840",
    "GBPUSD": "1.3320",
    "USDJPY": "150.20",
    "USDCHF": "0.8020",
    "AUDUSD": "0.6610",
    "USDCAD": "1.3780",
    "NZDUSD": "0.5820",
    "EURJPY": "162.80",
    "GBPJPY": "200.10",
    "EURGBP": "0.8140",
}


def _noise(t: float, seed: float) -> float:
    """Deterministic pseudo-random number in [-1, 1] for a time stamp."""
    x = math.sin(t * 12.9898 + seed * 78.233) * 43758.5453
    return (x - math.floor(x)) * 2 - 1


def _wave(t: float, seed: float) -> float:
    """Smooth relative move around 0 (a few tenths of a percent), continuous in time."""
    day = 86400.0
    return (
        0.006 * math.sin(2 * math.pi * t / (5.3 * day) + seed)
        + 0.003 * math.sin(2 * math.pi * t / (1.1 * day) + seed * 1.7)
        + 0.0012 * math.sin(2 * math.pi * t / (3.3 * 3600) + seed * 0.3)
        + 0.0004 * _noise(math.floor(t / 300), seed)
    )


def mock_bars(
    code: str, base: Decimal, timeframe: str, end: int, count: int, digits: int
) -> list[Bar]:
    step = TF_SECONDS[timeframe]
    seed = (sum(ord(c) for c in code) % 97) / 10
    quant = Decimal(1).scaleb(-digits)
    b = float(base)
    bars: list[Bar] = []
    t = end - end % step
    while len(bars) < count:
        weekday = datetime.fromtimestamp(t, UTC).weekday()
        if step >= 604800 or weekday < 5:  # markets closed on the weekend
            samples = [b * (1 + _wave(t + step * k / 6, seed)) for k in range(7)]
            o, c = samples[0], samples[-1]
            hi = max(samples) * (1 + 0.0003 * abs(_noise(t, seed + 1)))
            lo = min(samples) * (1 - 0.0003 * abs(_noise(t, seed + 2)))
            bars.append(
                Bar(
                    time=t,
                    open=Decimal(o).quantize(quant),
                    high=Decimal(hi).quantize(quant),
                    low=Decimal(lo).quantize(quant),
                    close=Decimal(c).quantize(quant),
                    volume=int(500 + 400 * abs(_noise(t, seed + 3))),
                )
            )
        t -= step
    bars.reverse()
    return bars


async def _base_price(session: AsyncSession, ctx: AccessContext, symbol: Symbol) -> Decimal:
    """Centre the mock chart on the trader's own latest plan / analysis level of the symbol."""
    entry = await session.scalar(
        select(TradePlan.entry_price)
        .where(TradePlan.user_id == ctx.owner_id, TradePlan.symbol_id == symbol.id)
        .order_by(TradePlan.created_at.desc())
        .limit(1)
    )
    if entry is not None:
        return Decimal(entry)
    levels = await session.scalar(
        select(MarketAnalysis.key_levels)
        .where(MarketAnalysis.user_id == ctx.owner_id, MarketAnalysis.symbol_id == symbol.id)
        .order_by(MarketAnalysis.updated_at.desc())
        .limit(1)
    )
    if levels:
        prices: Sequence[Decimal] = [Decimal(str(lv["price"])) for lv in levels]
        return sum(prices, Decimal(0)) / len(prices)
    return Decimal(DEFAULT_PRICE.get(symbol.code, "100"))


async def ohlc(
    session: AsyncSession,
    ctx: AccessContext,
    *,
    symbol_id: uuid.UUID,
    timeframe: str,
    to: int | None,
    count: int,
) -> OhlcOut:
    symbol = await _symbol(session, symbol_id)
    end = to if to is not None else int(datetime.now(UTC).timestamp())
    # Real bars from the trader's broker (EA / cTrader, F-08 AC5) when any are stored.
    real = await market_data.chart_bars(session, symbol.id, timeframe, end, count)
    if real is not None:
        return OhlcOut(
            symbol_id=symbol.id,
            symbol_code=symbol.code,
            timeframe=timeframe,
            digits=symbol.digits,
            source="ctrader" if real.platform == "ctrader" else "mt5",
            bars=[
                Bar(time=t, open=o, high=h, low=lo, close=c, volume=v)
                for t, o, h, lo, c, v in real.bars
            ],
        )
    base = await _base_price(session, ctx, symbol)
    return OhlcOut(
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        timeframe=timeframe,
        digits=symbol.digits,
        source="mock",
        bars=mock_bars(symbol.code, base, timeframe, end, count, symbol.digits),
    )
