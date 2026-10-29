from __future__ import annotations

import json
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from app.modules.plans.schemas import PlanBrief
from app.modules.playbook.schemas import SessionName, Timeframe

Bias = Literal["bull", "bear", "range"]
LevelKind = Literal["support", "resistance", "zone", "liquidity", "other"]
PriceIn = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
MAX_NARRATIVE_BYTES = 100_000
EMPTY_DOC: dict[str, Any] = {"type": "doc", "content": []}


def _unique[T](values: list[T]) -> list[T]:
    return list(dict.fromkeys(values))


def _strip(value: str) -> str:
    return value.strip()


def _narrative(value: dict[str, Any]) -> dict[str, Any]:
    """A Tiptap/ProseMirror JSON document (`{"type": "doc", "content": [...]}`)."""
    if value.get("type") != "doc" or not isinstance(value.get("content", []), list):
        raise ValueError("narrative must be a rich-text document")
    if len(json.dumps(value, ensure_ascii=False).encode()) > MAX_NARRATIVE_BYTES:
        raise ValueError("narrative is too long")
    return value


Narrative = Annotated[dict[str, Any], AfterValidator(_narrative)]


def narrative_text(doc: dict[str, Any]) -> str:
    """Plain text of a document: text nodes joined, one line per block."""
    blocks: list[str] = []

    def walk(node: dict[str, Any], out: list[str]) -> None:
        if node.get("type") == "text":
            out.append(str(node.get("text", "")))
        elif node.get("type") == "hardBreak":
            out.append("\n")
        for child in node.get("content", []) or []:
            if isinstance(child, dict):
                walk(child, out)

    for block in doc.get("content", []) or []:
        if isinstance(block, dict):
            parts: list[str] = []
            walk(block, parts)
            text = "".join(parts).strip()
            if text:
                blocks.append(text)
    return "\n".join(blocks)


class KeyLevel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: PriceIn
    price_to: PriceIn | None = None  # a zone: price … price_to
    kind: LevelKind = "other"
    label: Annotated[str, Field(max_length=100), AfterValidator(_strip)] = ""

    @model_validator(mode="after")
    def _order(self) -> KeyLevel:
        if self.price_to is not None:
            if self.price_to == self.price:
                self.price_to = None
            elif self.price_to < self.price:
                self.price, self.price_to = self.price_to, self.price
        return self


KeyLevels = Annotated[list[KeyLevel], Field(max_length=30)]
Timeframes = Annotated[list[Timeframe], Field(max_length=8), AfterValidator(_unique)]


class AnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID | None = None
    symbol_id: uuid.UUID
    analysis_date: date | None = None  # today in the user's timezone when omitted
    htf_bias: Bias
    key_levels: KeyLevels = []
    timeframes: Timeframes = []
    session: SessionName | None = None
    narrative: Narrative = EMPTY_DOC
    confidence: Annotated[int, Field(ge=1, le=10)] = 5


class AnalysisUpdate(BaseModel):
    """Omitted fields keep their value; `account_id: null` detaches the account."""

    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID | None = None
    symbol_id: uuid.UUID | None = None
    analysis_date: date | None = None
    htf_bias: Bias | None = None
    key_levels: KeyLevels | None = None
    timeframes: Timeframes | None = None
    session: SessionName | None = None
    narrative: Narrative | None = None
    confidence: Annotated[int, Field(ge=1, le=10)] | None = None


class KeyLevelOut(BaseModel):
    price: Decimal
    price_to: Decimal | None
    kind: LevelKind
    label: str


class AnalysisSummary(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID | None
    symbol_id: uuid.UUID
    symbol_code: str
    analysis_date: date
    htf_bias: Bias
    key_levels: list[KeyLevelOut]
    timeframes: list[str]
    session: str | None
    confidence: int
    narrative_text: str
    plan_count: int
    updated_at: datetime


class AnalysisOut(AnalysisSummary):
    narrative: dict[str, Any]
    created_at: datetime
    plans: list[PlanBrief]


# ------------------------------------------------------------------ chart drawings

DrawingTool = Literal["trendline", "ray", "horizontal", "rectangle", "text", "measure"]
DrawingOwner = Literal["analysis", "plan"]
POINTS_PER_TOOL: dict[str, int] = {
    "trendline": 2,
    "ray": 2,
    "horizontal": 1,
    "rectangle": 2,
    "text": 1,
    "measure": 2,
}


class ChartPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Annotated[int, Field(ge=0, le=4_102_444_800)]  # unix seconds (bar time)
    price: PriceIn


class DrawingStyle(BaseModel):
    """Colour is a design token name, never a raw value (both themes must work)."""

    model_config = ConfigDict(extra="forbid")
    color: Literal["brand", "plan", "profit", "loss", "warning", "ink"] = "brand"
    line: Literal["solid", "dashed", "dotted"] = "solid"
    width: Annotated[int, Field(ge=1, le=4)] = 1


class DrawingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = None  # keep the client id so the editor can match it up
    tool: DrawingTool
    timeframe: Timeframe
    points: Annotated[list[ChartPoint], Field(min_length=1, max_length=2)]
    style: DrawingStyle = DrawingStyle()
    text: Annotated[str, Field(max_length=200), AfterValidator(_strip)] = ""

    @model_validator(mode="after")
    def _shape(self) -> DrawingIn:
        need = POINTS_PER_TOOL[self.tool]
        if len(self.points) != need:
            raise ValueError(f"{self.tool} needs {need} point(s)")
        if self.tool == "text" and not self.text:
            raise ValueError("text drawing needs text")
        return self


class DrawingsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    drawings: Annotated[list[DrawingIn], Field(max_length=200)]


class DrawingOut(BaseModel):
    id: uuid.UUID
    tool: DrawingTool
    timeframe: str
    points: list[ChartPoint]
    style: DrawingStyle
    text: str


# ------------------------------------------------------------------ market data


class Bar(BaseModel):
    time: int  # unix seconds, bar open
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class OhlcOut(BaseModel):
    symbol_id: uuid.UUID
    symbol_code: str
    timeframe: str
    digits: int
    # "mock" until broker OHLC arrives with sync in Phase 4 (then "mt5" / "ctrader").
    source: Literal["mock", "mt5", "ctrader"]
    bars: list[Bar]
