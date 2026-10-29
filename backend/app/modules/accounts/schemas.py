from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Platform = Literal["mt5", "ctrader", "manual"]
AccountType = Literal["live", "demo", "prop"]
Severity = Literal["low", "medium", "high"]
Currency = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Pct = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]


def _strip(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


Text = Annotated[str, AfterValidator(_strip)]


# ------------------------------------------------------------------ accounts


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[Text, Field(max_length=100)]
    broker: Annotated[Text, Field(max_length=100)]
    platform: Platform
    account_type: AccountType
    account_number: Annotated[str, Field(max_length=50)] | None = None
    currency: Currency = "USD"
    initial_balance: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
    # Optional risk limits at creation (onboarding sets both in one step); defaults otherwise.
    risk_profile: RiskProfileIn | None = None


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[Text, Field(max_length=100)] | None = None
    broker: Annotated[Text, Field(max_length=100)] | None = None
    platform: Platform | None = None
    account_type: AccountType | None = None
    account_number: Annotated[str, Field(max_length=50)] | None = None
    currency: Currency | None = None
    initial_balance: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)] | None = None


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    broker: str
    platform: Platform
    account_type: AccountType
    account_number: str | None
    currency: str
    initial_balance: Decimal
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    # Reported by a connected broker (EA heartbeat / cTrader); null for manual accounts.
    last_balance: Decimal | None = None
    last_equity: Decimal | None = None
    last_equity_at: datetime | None = None


# ------------------------------------------------------------------ risk profile


class RiskProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_per_trade_pct: Annotated[Decimal, Field(gt=0, le=10, max_digits=5, decimal_places=2)]
    max_daily_loss_pct: Pct
    max_drawdown_pct: Pct
    max_trades_per_day: Annotated[int, Field(ge=1, le=100)]
    revenge_cooldown_min: Annotated[int, Field(ge=0, le=1440)]
    news_blackout_min: Annotated[int, Field(ge=0, le=240)]

    @model_validator(mode="after")
    def _consistent(self) -> RiskProfileIn:
        if self.max_daily_loss_pct > self.max_drawdown_pct:
            raise ValueError("max_daily_loss_pct cannot exceed max_drawdown_pct")
        if self.risk_per_trade_pct > self.max_daily_loss_pct:
            raise ValueError("risk_per_trade_pct cannot exceed max_daily_loss_pct")
        return self


class _RiskValuesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    risk_per_trade_pct: Decimal
    max_daily_loss_pct: Decimal
    max_drawdown_pct: Decimal
    max_trades_per_day: int
    revenge_cooldown_min: int
    news_blackout_min: int
    version: int


class RiskProfileOut(_RiskValuesOut):
    updated_at: datetime


class RiskProfileVersionOut(_RiskValuesOut):
    """One past or current set of limits; trades point at the version they were opened under."""

    id: uuid.UUID
    valid_from: datetime


class Usage(BaseModel):
    used: Decimal
    limit: Decimal


class RiskStatusOut(BaseModel):
    """Today's use of the limits (Accounts > "today" card) from closed / opened trades."""

    currency: str
    balance: Decimal
    equity: Decimal
    daily_loss: Usage
    drawdown_pct: Usage
    trades_today: Usage


# ------------------------------------------------------------------ rules

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class NoTradingWindowParams(BaseModel):
    """No new trades on `days` (0 = Monday) from `after` (local time) until end of day."""

    model_config = ConfigDict(extra="forbid")
    days: Annotated[list[Annotated[int, Field(ge=0, le=6)]], Field(min_length=1, max_length=7)]
    after: Annotated[str, Field(pattern=_TIME.pattern)]


class MaxLotVsPlanParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ratio: Annotated[Decimal, Field(gt=1, le=10, max_digits=4, decimal_places=2)]


class MaxConsecutiveLossesParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: Annotated[int, Field(ge=1, le=20)]


class CustomRuleParams(BaseModel):
    """Free-text rule the trader checks themselves (not evaluated automatically)."""

    model_config = ConfigDict(extra="forbid")
    text: Annotated[Text, Field(max_length=200)]


RULE_PARAMS: dict[str, type[BaseModel]] = {
    "no_trading_window": NoTradingWindowParams,
    "max_lot_vs_plan": MaxLotVsPlanParams,
    "max_consecutive_losses": MaxConsecutiveLossesParams,
    "custom": CustomRuleParams,
}
RuleCode = Literal["no_trading_window", "max_lot_vs_plan", "max_consecutive_losses", "custom"]


def _validate_params(code: str, params: dict[str, Any]) -> dict[str, Any]:
    return RULE_PARAMS[code].model_validate(params).model_dump(mode="json")


class RuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: RuleCode
    params: dict[str, Any]
    severity: Severity = "medium"
    is_active: bool = True

    @model_validator(mode="after")
    def _params(self) -> RuleCreate:
        self.params = _validate_params(self.code, self.params)
        return self


class RuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    params: dict[str, Any] | None = None
    severity: Severity | None = None
    is_active: bool | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: RuleCode
    params: dict[str, Any]
    severity: Severity
    is_active: bool
    created_by: Literal["trader", "mentor"]
    created_at: datetime


# ------------------------------------------------------------------ symbol overrides


class SymbolOverrideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    broker_symbol: Annotated[str, Field(min_length=1, max_length=32, pattern=r"^\S+$")]
    symbol_id: uuid.UUID
    contract_size: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)] | None = None
    tick_value: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)] | None = None


class SymbolOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    broker_symbol: str
    symbol_id: uuid.UUID
    symbol_code: str
    contract_size: Decimal | None
    tick_value: Decimal | None


class SymbolResolveOut(BaseModel):
    broker_symbol: str
    symbol_id: uuid.UUID
    symbol_code: str
    contract_size: Decimal
    tick_value: Decimal | None
    source: Literal["override", "standard"]


# ------------------------------------------------------------------ audit


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    entity: str
    entity_id: uuid.UUID
    actor_id: uuid.UUID | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    created_at: datetime


AccountCreate.model_rebuild()
