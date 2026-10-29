"""Market analysis + chart drawings (spec §2.5, F-05, F-19 AC3)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

BIASES = ("bull", "bear", "range")
OWNER_TYPES = ("analysis", "plan", "position")
DRAWING_TOOLS = ("trendline", "ray", "horizontal", "rectangle", "text", "measure")


class MarketAnalysis(Base):
    __tablename__ = "market_analyses"
    __table_args__ = (
        CheckConstraint(f"htf_bias IN {BIASES}", name="htf_bias"),
        CheckConstraint("confidence BETWEEN 1 AND 10", name="confidence"),
        Index("ix_market_analyses_user_date", "user_id", "analysis_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="SET NULL"), index=True
    )
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"))
    analysis_date: Mapped[date] = mapped_column(Date)
    htf_bias: Mapped[str] = mapped_column(String(10))
    # [{"price": "4366", "price_to": null | "4388",
    #   "kind": "support|resistance|zone|liquidity|other",
    #   "label": "H4 swing low"}]
    key_levels: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    timeframes: Mapped[list[str]] = mapped_column(ARRAY(String(5)), default=list)
    session: Mapped[str | None] = mapped_column(String(20))
    # Rich text as a ProseMirror/Tiptap JSON document; `narrative_text` is its plain text
    # (previews, search, AI coach input).
    narrative: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    narrative_text: Mapped[str] = mapped_column(Text, default="", server_default="")
    confidence: Mapped[int] = mapped_column(Integer)


class ChartDrawing(Base):
    """One drawing anchored in time/price, so it shows on every timeframe of the symbol."""

    __tablename__ = "chart_drawings"
    __table_args__ = (
        CheckConstraint(f"owner_type IN {OWNER_TYPES}", name="owner_type"),
        CheckConstraint(f"tool IN {DRAWING_TOOLS}", name="tool"),
        Index("ix_chart_drawings_owner", "owner_type", "owner_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    owner_type: Mapped[str] = mapped_column(String(10))
    owner_id: Mapped[uuid.UUID] = mapped_column()
    symbol_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("symbols.id", ondelete="RESTRICT"))
    timeframe: Mapped[str] = mapped_column(String(5))  # where it was drawn
    tool: Mapped[str] = mapped_column(String(12))
    # {"points": [{"time": 1760000000, "price": "4380.5"}], "style": {...}, "text": "..."}
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
