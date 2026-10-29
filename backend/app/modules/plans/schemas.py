from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.modules.playbook.schemas import RiskPct

Direction = Literal["long", "short"]
EntryType = Literal["market", "limit", "stop"]
PlanStatus = Literal[
    "draft", "locked", "triggered", "closed", "skipped", "missed", "invalidated", "expired"
]
PriceIn = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
Score = Annotated[int, Field(ge=1, le=10)]


def _strip(value: str) -> str:
    return value.strip()


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class TakeProfitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: PriceIn
    pct: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)] = Decimal(100)


class ManagementPlan(BaseModel):
    """Which of the setup's management rules this plan follows (adherence checks them, F-13)."""

    model_config = ConfigDict(extra="forbid")
    partial: bool = False
    break_even: bool = False
    trailing: bool = False


class ChecklistAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checklist_item_id: uuid.UUID
    checked: bool
    note: Annotated[str, Field(max_length=300), AfterValidator(_strip)] = ""


class EmotionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: Score | None = None
    confidence: Score | None = None
    tags: Annotated[list[uuid.UUID], Field(max_length=12)] = []
    note: Annotated[str, Field(max_length=2000), AfterValidator(_strip)] = ""


class EmotionOut(BaseModel):
    mood: int | None
    confidence: int | None
    tags: list[uuid.UUID]
    note: str
    logged_at: datetime


TakeProfits = Annotated[list[TakeProfitIn], Field(min_length=1, max_length=5)]
Invalidation = Annotated[str, Field(max_length=300), AfterValidator(_strip)]
Scenario = Annotated[str, Field(pattern=r"^[A-Z]$")]


class _Levels(BaseModel):
    @model_validator(mode="after")
    def _tp_share(self) -> _Levels:
        tps: list[TakeProfitIn] | None = getattr(self, "take_profits", None)
        if tps and sum((tp.pct for tp in tps), Decimal(0)) > 100:
            raise ValueError("take-profit shares exceed 100%")
        return self


class PlanCreate(_Levels):
    """F-06 AC1: setup, direction, entry, SL, at least one TP and risk % are required."""

    model_config = ConfigDict(extra="forbid")

    analysis_id: uuid.UUID | None = None
    setup_id: uuid.UUID
    account_id: uuid.UUID
    symbol_id: uuid.UUID
    direction: Direction
    scenario_label: Scenario | None = None  # next free letter of the analysis when omitted
    entry_type: EntryType = "limit"
    entry_price: PriceIn
    stop_loss: PriceIn
    take_profits: TakeProfits
    planned_risk_pct: RiskPct
    quote_to_account_rate: Annotated[Decimal, Field(gt=0)] | None = None
    management_plan: ManagementPlan = ManagementPlan()
    invalidation: Invalidation = ""
    valid_until: datetime | None = None  # end of the plan day (user's timezone) when omitted
    plan_date: date | None = None  # analysis date, else today in the user's timezone
    checklist_answers: Annotated[list[ChecklistAnswerIn], Field(max_length=30)] = []
    pre_emotion: EmotionIn | None = None


class PlanUpdate(_Levels):
    """Draft only. Omitted fields keep their value."""

    model_config = ConfigDict(extra="forbid")

    setup_id: uuid.UUID | None = None
    direction: Direction | None = None
    scenario_label: Scenario | None = None
    entry_type: EntryType | None = None
    entry_price: PriceIn | None = None
    stop_loss: PriceIn | None = None
    take_profits: TakeProfits | None = None
    planned_risk_pct: RiskPct | None = None
    quote_to_account_rate: Annotated[Decimal, Field(gt=0)] | None = None
    management_plan: ManagementPlan | None = None
    invalidation: Invalidation | None = None
    valid_until: datetime | None = None
    checklist_answers: Annotated[list[ChecklistAnswerIn], Field(max_length=30)] | None = None


class RevisionChanges(_Levels):
    """What a revision may change after the lock. The checklist stays as it was locked."""

    model_config = ConfigDict(extra="forbid")

    entry_type: EntryType | None = None
    entry_price: PriceIn | None = None
    stop_loss: PriceIn | None = None
    take_profits: TakeProfits | None = None
    planned_risk_pct: RiskPct | None = None
    management_plan: ManagementPlan | None = None
    invalidation: Invalidation | None = None
    valid_until: datetime | None = None


class RevisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: RevisionChanges
    # F-06 AC4: a reason is always required.
    reason: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_required_text)]


class RevisionPreviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: RevisionChanges


class StatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["skipped", "missed", "invalidated"]
    reason: Annotated[str, Field(min_length=1, max_length=500), AfterValidator(_required_text)]


class TakeProfitOut(BaseModel):
    price: Decimal
    pct: Decimal
    rr: Decimal | None = None


class ChecklistItemState(BaseModel):
    id: uuid.UUID
    text: str
    is_required: bool
    checked: bool
    note: str


class ChecklistStatus(BaseModel):
    done: int
    total: int
    required_done: int
    required_total: int
    missing: list[uuid.UUID]  # required items not ticked


class CalcMeta(BaseModel):
    """Inputs behind the planned numbers ("Balance $101,240 · contract 100 · tick value $1.00")."""

    balance: Decimal
    currency: str
    contract_size: Decimal
    value_per_point: Decimal
    tick_value_source: Literal["override", "standard"]


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None
    revision_no: int
    snapshot_hash: str
    changes: dict[str, dict[str, object]]
    risk_delta_amount: Decimal | None
    risk_delta_r: Decimal | None
    reason: str | None
    changed_at: datetime
    changed_after_entry: bool


class PlanBrief(BaseModel):
    """Row in Today's plan table and the analysis' plan list."""

    id: uuid.UUID
    analysis_id: uuid.UUID | None
    account_id: uuid.UUID
    symbol_id: uuid.UUID
    symbol_code: str
    setup_id: uuid.UUID
    setup_name: str
    plan_date: date
    scenario_label: str
    direction: Direction
    entry_type: EntryType
    entry_price: Decimal
    stop_loss: Decimal
    take_profits: list[TakeProfitOut]
    planned_risk_pct: Decimal
    planned_risk_amount: Decimal
    planned_lot: Decimal
    planned_rr: Decimal | None
    status: PlanStatus
    locked_at: datetime | None
    valid_until: datetime | None
    checklist: ChecklistStatus


class PlanOut(PlanBrief):
    quote_to_account_rate: Decimal | None
    management_plan: ManagementPlan
    invalidation: str
    status_reason: str | None
    status_changed_at: datetime | None
    lock_hash: str | None
    triggered_at: datetime | None
    current_revision: int
    current_hash: str | None  # hash of the latest revision (equals lock_hash at rev 1)
    currency: str
    calc: CalcMeta | None  # None when the inputs can no longer be valued (e.g. missing FX rate)
    checklist_items: list[ChecklistItemState]
    pre_emotion: EmotionOut | None
    revisions: list[RevisionOut]
    can_lock: bool
    created_at: datetime
    updated_at: datetime
