"""emotion_tags reference table (spec §2.3, user_id NULL = system tag) + emotion_logs (§2.7)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

VALENCES = ("pos", "neg", "neutral")
LOG_OWNER_TYPES = ("plan", "position", "day")
PHASES = ("pre", "in", "post", "daily")


class EmotionTag(Base):
    __tablename__ = "emotion_tags"
    __table_args__ = (
        CheckConstraint(f"valence IN {VALENCES}", name="valence"),
        # System codes are unique among system tags; custom codes unique per user.
        Index(
            "uq_emotion_tags_system_code",
            "code",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
        Index(
            "uq_emotion_tags_user_code",
            "user_id",
            "code",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
    )

    code: Mapped[str] = mapped_column(String(50))
    label_th: Mapped[str] = mapped_column(String(100))
    label_en: Mapped[str] = mapped_column(String(100))
    valence: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )


class EmotionLog(Base):
    """Pre (plan), in/post (position, Phase 5) and daily mood (F-11).

    Daily entries: owner_type="day", owner_id = user id, `log_date` = the local day."""

    __tablename__ = "emotion_logs"
    __table_args__ = (
        CheckConstraint(f"owner_type IN {LOG_OWNER_TYPES}", name="owner_type"),
        CheckConstraint(f"phase IN {PHASES}", name="phase"),
        CheckConstraint("mood IS NULL OR mood BETWEEN 1 AND 10", name="mood"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 1 AND 10", name="confidence"),
        Index("ix_emotion_logs_owner", "owner_type", "owner_id"),
        # One pre-trade log per plan, one daily entry per day.
        Index(
            "uq_emotion_logs_pre",
            "owner_id",
            unique=True,
            postgresql_where=text("phase = 'pre'"),
        ),
        Index(
            "uq_emotion_logs_daily",
            "user_id",
            "log_date",
            unique=True,
            postgresql_where=text("phase = 'daily'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    owner_type: Mapped[str] = mapped_column(String(10))
    owner_id: Mapped[uuid.UUID] = mapped_column()
    phase: Mapped[str] = mapped_column(String(6))
    mood: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[int | None] = mapped_column(Integer)
    # emotion_tags ids (system or the user's own).
    tags: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(Uuid), default=list)
    trigger_event: Mapped[str | None] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(2000), default="", server_default="")
    log_date: Mapped[date | None] = mapped_column(Date)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
