"""Broker OHLC: idempotent storage (F-08 AC5), MAE/MFE ranges, chart bars."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import TradingAccount
from app.modules.market_data.models import TIMEFRAMES, ohlc_bars

TF_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
# asyncpg caps a statement at 32 767 parameters; 9 per bar.
_CHUNK = 3000


@dataclass(frozen=True, slots=True)
class BarIn:
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


async def upsert_bars(
    session: AsyncSession,
    *,
    symbol_id: uuid.UUID,
    timeframe: str,
    bars: Sequence[BarIn],
    source_account_id: uuid.UUID | None,
) -> int:
    """Insert bars not stored yet (first broker wins). Returns how many were new."""
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"unsupported timeframe {timeframe}")
    inserted = 0
    rows = [
        {
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "ts": b.ts,
            "open": b.open,
            "high": b.high,
            "low": b.low,
            "close": b.close,
            "volume": b.volume,
            "source_account_id": source_account_id,
        }
        for b in bars
    ]
    for i in range(0, len(rows), _CHUNK):
        stmt = (
            insert(ohlc_bars)
            .values(rows[i : i + _CHUNK])
            .on_conflict_do_nothing(index_elements=["symbol_id", "timeframe", "ts"])
            .returning(ohlc_bars.c.ts)
        )
        inserted += len((await session.execute(stmt)).all())
    return inserted


@dataclass(frozen=True, slots=True)
class PriceRange:
    high: Decimal
    low: Decimal
    timeframe: str


async def price_range(
    session: AsyncSession, symbol_id: uuid.UUID, start: datetime, end: datetime
) -> PriceRange | None:
    """Highest high / lowest low between `start` and `end` from the finest timeframe that covers
    the period. The bar containing `start` is included, so its earlier part counts too."""
    for tf in TIMEFRAMES:
        step = timedelta(seconds=TF_SECONDS[tf])
        stmt = select(
            func.max(ohlc_bars.c.high), func.min(ohlc_bars.c.low), func.min(ohlc_bars.c.ts)
        ).where(
            ohlc_bars.c.symbol_id == symbol_id,
            ohlc_bars.c.timeframe == tf,
            ohlc_bars.c.ts > start - step,
            ohlc_bars.c.ts <= end,
        )
        high, low, first = (await session.execute(stmt)).one()
        if high is not None and first is not None and first <= start:
            return PriceRange(high=Decimal(high), low=Decimal(low), timeframe=tf)
    return None


@dataclass(frozen=True, slots=True)
class ChartBars:
    platform: str  # platform of the account that delivered them (mt5 / ctrader)
    bars: list[tuple[int, Decimal, Decimal, Decimal, Decimal, int]]


async def chart_bars(
    session: AsyncSession, symbol_id: uuid.UUID, timeframe: str, end: int, count: int
) -> ChartBars | None:
    """Latest `count` stored bars up to `end` (unix s), oldest first; None if there are none."""
    if timeframe not in TIMEFRAMES:
        return None
    stmt = (
        select(ohlc_bars, TradingAccount.platform)
        .outerjoin(TradingAccount, TradingAccount.id == ohlc_bars.c.source_account_id)
        .where(
            ohlc_bars.c.symbol_id == symbol_id,
            ohlc_bars.c.timeframe == timeframe,
            ohlc_bars.c.ts <= datetime.fromtimestamp(end, UTC),
        )
        .order_by(ohlc_bars.c.ts.desc())
        .limit(count)
    )
    rows = (await session.execute(stmt)).all()
    if not rows:
        return None
    platform = next((r.platform for r in rows if r.platform), "mt5")
    bars = [(int(r.ts.timestamp()), r.open, r.high, r.low, r.close, int(r.volume)) for r in rows]
    bars.reverse()
    return ChartBars(platform=platform, bars=bars)
