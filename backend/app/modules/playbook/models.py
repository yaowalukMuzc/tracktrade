"""Playbook: setups with checklist, management rules and example images (spec §2.4, F-04)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "H4", "D1", "W1")
SESSIONS = ("asia", "london", "new_york")


class Setup(Base):
    __tablename__ = "setups"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    timeframes: Mapped[list[str]] = mapped_column(ARRAY(String(5)), default=list)
    sessions: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    default_risk_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    # {"partial": {"pct": 50, "at_r": 1.5} | null, "break_even": {"at_r": 1} | null,
    #  "trailing": {"method": "Swing low M15"} | null}
    management_rules: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # Used setups are archived, never deleted (F-04 AC2): trade plans reference them with
    # ON DELETE RESTRICT, so a delete of a used setup fails -> 409 setup_in_use.
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))


class SetupChecklistItem(Base):
    __tablename__ = "setup_checklist_items"

    setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setups.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(String(200))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)


class SetupExample(Base):
    __tablename__ = "setup_examples"

    setup_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("setups.id", ondelete="CASCADE"), index=True
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attachments.id", ondelete="RESTRICT"), unique=True
    )
    note: Mapped[str] = mapped_column(String(200), default="", server_default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
