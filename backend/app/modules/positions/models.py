"""Positions, executions (fills) and SL/TP modifications (spec §2.6, F-07, F-08, F-10)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, Money, Price

DIRECTIONS = ("long", "short")
SOURCES = ("manual", "mt5", "ctrader", "ocr")
STATUSES = ("open", "closed")
# auto = engine linked it (or found it unplanned with certainty); manual = the trader chose;
# pending = several / no candidate plans -> waits in the match queue (F-10 AC2).
MATCH_STATUSES = ("auto", "manual", "pending")
SIDES = ("in", "out")
MOD_FIELDS = ("sl", "tp")
RISK_DIRECTIONS = ("increase", "decrease", "neutral")
Lot = Numeric(10, 2)


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (
        CheckConstraint(f"direction IN {DIRECTIONS}", name="direction"),
        CheckConstraint(f"source IN {SOURCES}", name="source"),
        CheckConstraint(f"status IN {STATUSES}", name="status"),
        CheckConstraint(f"match_status IN {MATCH_STATUSES}", name="match_status"),
        # Same broker position never imported twice (F-08 AC3). NULLs (manual) don't collide.
        UniqueConstraint("account_id", "broker_position_id"),
        # "#T-1042" running number per trader (PLAN M12).
        UniqueConstraint("user_id", "ref_no"),
        Index("ix_positions_user_opened", "user_id", "opened_at"),
        Index("ix_positions_account_closed", "account_id", "closed_at"),
        Index("ix_positions_user_match_status", "user_id", "match_status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="SET NULL"), index=True
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"))
    ref_no: Mapped[int] = mapped_column(Integer)
    direction: Mapped[str] = mapped_column(String(5))
    source: Mapped[str] = mapped_column(String(8))
    broker_position_id: Mapped[str | None] = mapped_column(String(64))
    broker_symbol: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(6), default="open")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Derived from executions by positions.calc (recomputed on every change).
    avg_entry: Mapped[Price]
    avg_exit: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    total_lot: Mapped[Decimal] = mapped_column(Lot)  # all volume that went in
    open_lot: Mapped[Decimal] = mapped_column(Lot)  # still open
    gross_pnl: Mapped[Money] = mapped_column(default=Decimal(0))
    commission: Mapped[Money] = mapped_column(default=Decimal(0))  # signed, cost < 0
    swap: Mapped[Money] = mapped_column(default=Decimal(0))
    net_pnl: Mapped[Money] = mapped_column(default=Decimal(0))
    initial_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    r_multiple: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    # Max adverse / favourable excursion while open, as price distances (>= 0), from OHLC.
    mae: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    mfe: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    initial_sl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    initial_tp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_sl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    current_tp: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    # Manual cross pairs (GBPJPY on a USD account) need the quote -> account rate.
    quote_to_account_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))

    # F-07 AC3: no plan, or the plan was locked after the entry.
    is_unplanned: Mapped[bool] = mapped_column(Boolean, default=True)
    match_status: Mapped[str] = mapped_column(String(7), default="pending")
    # What the matching engine saw (candidates + distances) — kept to validate the tolerance (S3).
    match_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Risk limits in force when the trade was opened (F-02 AC4).
    risk_profile_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("risk_profile_versions.id", ondelete="SET NULL")
    )


class Execution(Base):
    """One fill: an entry (scale-in) or an exit (partial / full close)."""

    __tablename__ = "executions"
    __table_args__ = (
        CheckConstraint(f"side IN {SIDES}", name="side"),
        CheckConstraint("lot > 0", name="lot_positive"),
        CheckConstraint("price > 0", name="price_positive"),
        # Idempotent ingest: a broker deal is stored once per account (F-08 AC3).
        UniqueConstraint("account_id", "broker_deal_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), index=True
    )
    broker_deal_id: Mapped[str | None] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(3))
    lot: Mapped[Decimal] = mapped_column(Lot)
    price: Mapped[Price]
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    commission: Mapped[Money] = mapped_column(default=Decimal(0))
    swap: Mapped[Money] = mapped_column(default=Decimal(0))
    # Profit the broker booked for this deal (exits) — preferred over our own maths when present.
    profit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))


class OrderModification(Base):
    """SL/TP change of an open position; `direction_of_risk` feeds adherence (Phase 6)."""

    __tablename__ = "order_modifications"
    __table_args__ = (
        CheckConstraint(f"field IN {MOD_FIELDS}", name="field"),
        CheckConstraint(f"direction_of_risk IN {RISK_DIRECTIONS}", name="direction_of_risk"),
        UniqueConstraint("account_id", "broker_event_id"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id", ondelete="CASCADE"), index=True
    )
    broker_event_id: Mapped[str | None] = mapped_column(String(96))
    field: Mapped[str] = mapped_column(String(2))
    old_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # None = not set
    new_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))  # None = removed
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    direction_of_risk: Mapped[str] = mapped_column(String(8))
    # The in-trade emotion prompt (F-11 AC2, Phase 5) is created from risk increases.
    prompted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
