"""Trading accounts, risk profiles, trading rules, symbol overrides (spec §2.2-2.3, F-02, F-03)."""

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
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, Money

PLATFORMS = ("mt5", "ctrader", "manual")
ACCOUNT_TYPES = ("live", "demo", "prop")
RULE_SEVERITIES = ("low", "medium", "high")
RULE_CREATORS = ("trader", "mentor")
Pct = Numeric(5, 2)

# F-02 AC2 defaults (+ cooldown / blackout from the design: 30 / 15 minutes).
RISK_DEFAULTS: dict[str, Any] = {
    "risk_per_trade_pct": Decimal("1.00"),
    "max_daily_loss_pct": Decimal("3.00"),
    "max_drawdown_pct": Decimal("10.00"),
    "max_trades_per_day": 5,
    "revenge_cooldown_min": 30,
    "news_blackout_min": 15,
}
RISK_FIELDS = tuple(RISK_DEFAULTS)


class TradingAccount(Base):
    __tablename__ = "trading_accounts"
    __table_args__ = (
        CheckConstraint(f"platform IN {PLATFORMS}", name="platform"),
        CheckConstraint(f"account_type IN {ACCOUNT_TYPES}", name="account_type"),
        CheckConstraint("initial_balance > 0", name="initial_balance_positive"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    broker: Mapped[str] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(10))
    account_type: Mapped[str] = mapped_column(String(10))
    account_number: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3))
    initial_balance: Mapped[Money]
    # Archive instead of delete (F-02 AC1): the account and its history stay.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Latest balance / equity reported by the broker (EA heartbeat, cTrader) — PLAN M26.
    last_balance: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    last_equity: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    last_equity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class _RiskValues:
    risk_per_trade_pct: Mapped[Decimal] = mapped_column(Pct)
    max_daily_loss_pct: Mapped[Decimal] = mapped_column(Pct)
    max_drawdown_pct: Mapped[Decimal] = mapped_column(Pct)
    max_trades_per_day: Mapped[int] = mapped_column(Integer)
    revenge_cooldown_min: Mapped[int] = mapped_column(Integer)
    news_blackout_min: Mapped[int] = mapped_column(Integer)


class RiskProfile(_RiskValues, Base):
    """Current limits of one account (1:1). Every change also appends a RiskProfileVersion."""

    __tablename__ = "risk_profiles"

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), unique=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)


class RiskProfileVersion(_RiskValues, Base):
    """Append-only history of a risk profile (F-02 AC4).

    A trade stores the id of the version in force when it was opened (Phase 4), so
    editing the profile never changes how older trades are evaluated.
    """

    __tablename__ = "risk_profile_versions"
    __table_args__ = (UniqueConstraint("account_id", "version"),)

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TradingRule(Base):
    """Extra rule on an account (`code` + `params`), checked by the rule engine in Phase 6."""

    __tablename__ = "trading_rules"
    __table_args__ = (
        CheckConstraint(f"severity IN {RULE_SEVERITIES}", name="severity"),
        CheckConstraint(f"created_by IN {RULE_CREATORS}", name="created_by"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(String(10), default="trader")
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))


class AccountSymbolOverride(Base):
    """Broker symbol name + optional broker-specific specs (F-03 AC2, PLAN R9)."""

    __tablename__ = "account_symbol_overrides"
    __table_args__ = (UniqueConstraint("account_id", "broker_symbol"),)

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE"), index=True
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"))
    broker_symbol: Mapped[str] = mapped_column(String(32))
    contract_size: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    # Value of one tick (= symbol point) for 1 lot, in the account currency (from MT5).
    tick_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
