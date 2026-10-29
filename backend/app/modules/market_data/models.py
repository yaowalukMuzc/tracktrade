"""OHLC bars from the trader's broker (spec §2.9, F-08 AC5).

A plain table (no uuid / timestamps) keyed by (symbol, timeframe, time) as in the spec: bars are
shared by every account of the same symbol, and the first broker to deliver a bar wins.
Monthly partitioning (spec) is left for Phase 7 performance work.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Numeric, String, Table, Uuid

from app.core.models_base import Base

TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1")

ohlc_bars = Table(
    "ohlc_bars",
    Base.metadata,
    Column("symbol_id", Uuid, ForeignKey("symbols.id", ondelete="CASCADE"), primary_key=True),
    Column("timeframe", String(3), primary_key=True),
    Column("ts", DateTime(timezone=True), primary_key=True),
    Column("open", Numeric(18, 6), nullable=False),
    Column("high", Numeric(18, 6), nullable=False),
    Column("low", Numeric(18, 6), nullable=False),
    Column("close", Numeric(18, 6), nullable=False),
    Column("volume", Numeric(18, 2), nullable=False),
    Column(
        "source_account_id",
        Uuid,
        ForeignKey("trading_accounts.id", ondelete="SET NULL"),
        nullable=True,
    ),
)
