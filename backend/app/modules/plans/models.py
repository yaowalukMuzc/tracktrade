"""Trade plans, append-only revisions, checklist answers (spec §2.5, F-06)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, Money, Price

DIRECTIONS = ("long", "short")
ENTRY_TYPES = ("market", "limit", "stop")
# draft → locked → triggered → closed, or skipped | missed | invalidated | expired (spec §1.7).
STATUSES = ("draft", "locked", "triggered", "closed", "skipped", "missed", "invalidated", "expired")


class TradePlan(Base):
    __tablename__ = "trade_plans"
    __table_args__ = (
        CheckConstraint(f"direction IN {DIRECTIONS}", name="direction"),
        CheckConstraint(f"entry_type IN {ENTRY_TYPES}", name="entry_type"),
        CheckConstraint(f"status IN {STATUSES}", name="status"),
        Index("ix_trade_plans_user_date", "user_id", "plan_date"),
        Index("ix_trade_plans_status_valid_until", "status", "valid_until"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("market_analyses.id", ondelete="SET NULL"), index=True
    )
    # F-04 AC2: a setup used by a plan cannot be deleted, only archived.
    setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setups.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"))
    plan_date: Mapped[date] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(5))
    scenario_label: Mapped[str] = mapped_column(String(2), default="A")
    entry_type: Mapped[str] = mapped_column(String(6))
    entry_price: Mapped[Price]
    stop_loss: Mapped[Price]
    take_profits: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # [{price, pct}]
    planned_risk_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    planned_risk_amount: Mapped[Money]
    planned_lot: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    planned_rr: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    quote_to_account_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    # {"partial": bool, "break_even": bool, "trailing": bool} — which setup rules apply.
    management_plan: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    invalidation: Mapped[str] = mapped_column(String(300), default="", server_default="")
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default="draft", server_default="draft")
    status_reason: Mapped[str | None] = mapped_column(String(500))
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_hash: Mapped[str | None] = mapped_column(String(64))  # sha256 of the rev-1 snapshot
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class TradePlanRevision(Base):
    """Append-only (F-06 AC4). Revision 1 is the lock itself; later ones need a reason."""

    __tablename__ = "trade_plan_revisions"
    __table_args__ = (UniqueConstraint("plan_id", "revision_no"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="CASCADE"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    snapshot_hash: Mapped[str] = mapped_column(String(64))
    # {"stop_loss": {"from": "4366.78", "to": "4360"}, ...}; empty for revision 1.
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    risk_delta_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    risk_delta_r: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # F-06 AC5: made after the entry → counted as a deviation by the adherence engine.
    changed_after_entry: Mapped[bool] = mapped_column(Boolean, default=False)


class PlanChecklistAnswer(Base):
    __tablename__ = "plan_checklist_answers"
    __table_args__ = (UniqueConstraint("plan_id", "checklist_item_id"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trade_plans.id", ondelete="CASCADE"), index=True
    )
    checklist_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setup_checklist_items.id", ondelete="CASCADE")
    )
    checked: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(300), default="", server_default="")
