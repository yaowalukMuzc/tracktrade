from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Timeframe = Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1"]
SessionName = Literal["asia", "london", "new_york"]
RiskPct = Annotated[Decimal, Field(gt=0, le=10, max_digits=5, decimal_places=2)]
RMultiple = Annotated[Decimal, Field(gt=0, le=20, max_digits=4, decimal_places=2)]


def _strip(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


def _unique[T](values: list[T]) -> list[T]:
    return list(dict.fromkeys(values))


Name = Annotated[str, Field(max_length=100), AfterValidator(_strip)]
ItemText = Annotated[str, Field(max_length=200), AfterValidator(_strip)]


class PartialRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pct: Annotated[Decimal, Field(gt=0, lt=100, max_digits=5, decimal_places=2)]
    at_r: RMultiple


class BreakEvenRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at_r: RMultiple


class TrailingRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Annotated[str, Field(max_length=100), AfterValidator(_strip)]


class ManagementRules(BaseModel):
    """What the adherence engine checks (F-13 AC4). A missing rule = not part of the plan."""

    model_config = ConfigDict(extra="forbid")
    partial: PartialRule | None = None
    break_even: BreakEvenRule | None = None
    trailing: TrailingRule | None = None


class ChecklistItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID | None = None  # keep an existing item (answers in plans point at it)
    text: ItemText
    is_required: bool = False


class SetupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    description: Annotated[str, Field(max_length=2000)] = ""
    timeframes: Annotated[list[Timeframe], Field(max_length=8), AfterValidator(_unique)] = []
    sessions: Annotated[list[SessionName], Field(max_length=3), AfterValidator(_unique)] = []
    default_risk_pct: RiskPct = Decimal("1.00")
    management_rules: ManagementRules = ManagementRules()
    checklist: Annotated[list[ChecklistItemIn], Field(max_length=30)] = []


class SetupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None
    timeframes: Annotated[list[Timeframe], Field(max_length=8), AfterValidator(_unique)] | None = (
        None
    )
    sessions: Annotated[list[SessionName], Field(max_length=3), AfterValidator(_unique)] | None = (
        None
    )
    default_risk_pct: RiskPct | None = None
    management_rules: ManagementRules | None = None


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    text: str
    is_required: bool


class ExampleOut(BaseModel):
    id: uuid.UUID
    attachment_id: uuid.UUID
    url: str
    note: str


class ExampleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attachment_id: uuid.UUID
    note: Annotated[str, Field(max_length=200)] = ""


class SetupStats(BaseModel):
    """F-04 AC3 — filled from trades in Phase 7; null until there is data."""

    trades: int = 0
    win_rate: Decimal | None = None
    expectancy_r: Decimal | None = None
    avg_adherence: Decimal | None = None
    avg_quality: Decimal | None = None
    avg_quality_grade: Literal["A", "B", "C", "D"] | None = None


class SetupSummary(BaseModel):
    id: uuid.UUID
    name: str
    timeframes: list[str]
    sessions: list[str]
    default_risk_pct: Decimal
    is_archived: bool
    checklist_count: int
    stats: SetupStats


class SetupOut(SetupSummary):
    description: str
    management_rules: ManagementRules
    checklist: list[ChecklistItemOut]
    examples: list[ExampleOut]
    created_at: datetime
    updated_at: datetime


class SetupCounts(BaseModel):
    active: int
    archived: int


class SetupListOut(BaseModel):
    items: list[SetupSummary]
    counts: SetupCounts
