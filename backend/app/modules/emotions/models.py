"""emotion_tags reference table (spec §2.3). user_id NULL = system tag."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

VALENCES = ("pos", "neg", "neutral")


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
