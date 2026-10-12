"""mistake_categories reference table (spec §2.3, F-15): 6 dimensions."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

DIMENSIONS = ("analysis", "planning", "execution", "risk", "discipline", "emotion")


class MistakeCategory(Base):
    __tablename__ = "mistake_categories"
    __table_args__ = (CheckConstraint(f"dimension IN {DIMENSIONS}", name="dimension"),)

    code: Mapped[str] = mapped_column(String(50), unique=True)
    dimension: Mapped[str] = mapped_column(String(20))
    label_th: Mapped[str] = mapped_column(String(150))
    label_en: Mapped[str] = mapped_column(String(150))
