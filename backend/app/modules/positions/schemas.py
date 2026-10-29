"""Positions API shapes (PLAN §6 positions / matching). Money and prices serialise as strings."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Direction = Literal["long", "short"]
Source = Literal["manual", "mt5", "ctrader", "ocr"]
Side = Literal["in", "out"]
Tab = Literal["all", "review", "pending", "unplanned", "open"]
MatchStatus = Literal["auto", "manual", "pending"]
# Why a trade counts as unplanned (F-07 AC3) — shown as the warning under the plan picker.
UnplannedReason = Literal["no_plan", "plan_not_locked", "locked_after_entry"]

PriceIn = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
LotIn = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
MoneyIn = Annotated[Decimal, Field(max_digits=18, decimal_places=2)]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp needs a timezone (ISO-8601 with Z or an offset)")
    return value


AwareDatetime = Annotated[datetime, AfterValidator(_aware)]


class ExecutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    side: Side
    lot: LotIn
    price: PriceIn
    executed_at: AwareDatetime
    commission: MoneyIn = Decimal(0)  # signed like the broker: a cost is negative
    swap: MoneyIn = Decimal(0)


class ManualPositionIn(BaseModel):
    """`POST /positions` (F-07). Plan: `plan_id` links it; `unplanned=true` records it as
    unplanned on purpose; neither → the matching engine decides (auto / match queue)."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    symbol_id: uuid.UUID
    direction: Direction
    initial_sl: PriceIn | None = None
    initial_tp: PriceIn | None = None
    executions: Annotated[list[ExecutionIn], Field(min_length=1, max_length=50)]
    plan_id: uuid.UUID | None = None
    unplanned: bool = False
    quote_to_account_rate: (
        Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=8)] | None
    ) = None

    @model_validator(mode="after")
    def _plan_choice(self) -> ManualPositionIn:
        if self.plan_id is not None and self.unplanned:
            raise ValueError("choose a plan or unplanned, not both")
        return self


class PlanRef(BaseModel):
    id: uuid.UUID
    scenario_label: str
    setup_id: uuid.UUID
    setup_name: str
    status: str
    entry_type: str
    entry_price: Decimal
    stop_loss: Decimal
    locked_at: datetime | None


class PositionSummary(BaseModel):
    """One row of the trades table / one TradeCard."""

    id: uuid.UUID
    ref_no: int
    account_id: uuid.UUID
    account_name: str
    currency: str
    symbol_id: uuid.UUID
    symbol_code: str
    digits: int
    direction: Direction
    source: Source
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: datetime | None
    avg_entry: Decimal
    avg_exit: Decimal | None
    total_lot: Decimal
    open_lot: Decimal
    net_pnl: Decimal
    r_multiple: Decimal | None
    current_sl: Decimal | None
    current_tp: Decimal | None
    is_unplanned: bool
    match_status: MatchStatus
    plan: PlanRef | None
    # Phase 5-6 fill these; the table shows "—" until then.
    adherence_pct: Decimal | None = None
    quality_grade: str | None = None
    quadrant: str | None = None
    review_status: Literal["pending", "done"] | None = None


class Counts(BaseModel):
    all: int
    review: int
    pending: int
    unplanned: int
    open: int


class PositionList(BaseModel):
    items: list[PositionSummary]
    total: int  # matching the tab + filters
    offset: int
    limit: int
    counts: Counts  # per tab, with the filters but without the tab


class ExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    side: Side
    lot: Decimal
    price: Decimal
    executed_at: datetime
    commission: Decimal
    swap: Decimal
    profit: Decimal | None
    broker_deal_id: str | None


class ModificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    field: Literal["sl", "tp"]
    old_value: Decimal | None
    new_value: Decimal | None
    modified_at: datetime
    direction_of_risk: Literal["increase", "decrease", "neutral"]


class PositionOut(PositionSummary):
    broker_position_id: str | None
    broker_symbol: str | None
    initial_sl: Decimal | None
    initial_tp: Decimal | None
    gross_pnl: Decimal
    commission: Decimal
    swap: Decimal
    initial_risk_amount: Decimal | None
    mae: Decimal | None
    mfe: Decimal | None
    mae_r: Decimal | None
    mfe_r: Decimal | None
    unplanned_reason: UnplannedReason | None
    matched_at: datetime | None
    match_meta: dict[str, Any]
    risk_profile_version: int | None
    executions: list[ExecutionOut]
    modifications: list[ModificationOut]


class PositionCalcOut(BaseModel):
    """`POST /positions/preview` — the "คำนวณให้อัตโนมัติ" card, nothing saved."""

    status: Literal["open", "closed"]
    avg_entry: Decimal
    avg_exit: Decimal | None
    total_lot: Decimal
    open_lot: Decimal
    gross_pnl: Decimal
    commission: Decimal
    swap: Decimal
    net_pnl: Decimal
    initial_risk_amount: Decimal | None
    r_multiple: Decimal | None
    currency: str
    unplanned_reason: UnplannedReason | None


class MatchCandidate(BaseModel):
    plan: PlanRef
    distance: Decimal
    pct_of_sl: Decimal
    within_price: bool
    within_time: bool
    eligible: bool
    recommended: bool


class MatchQueueItem(BaseModel):
    position: PositionSummary
    first_entry: Decimal
    candidates: list[MatchCandidate]


class MatchIn(BaseModel):
    """`plan_id: null` = record as unplanned (counts as a Discipline deviation)."""

    model_config = ConfigDict(extra="forbid")
    plan_id: uuid.UUID | None


class ListFilters(BaseModel):
    tab: Tab = "all"
    account_id: uuid.UUID | None = None
    symbol_id: uuid.UUID | None = None
    setup_id: uuid.UUID | None = None
    direction: Direction | None = None
    date_from: date | None = None  # opened on/after (trader's timezone)
    date_to: date | None = None  # opened on/before
    q: Annotated[str, Field(max_length=60)] = ""
