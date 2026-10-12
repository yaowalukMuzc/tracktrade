"""users table (spec §2.1 + PLAN M19 `theme`)."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

LOCALES = ("th", "en")
THEMES = ("light", "dark", "system")
PLAN_TIERS = ("free", "pro")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"locale IN {LOCALES}", name="locale"),
        CheckConstraint(f"theme IN {THEMES}", name="theme"),
        CheckConstraint(f"plan_tier IN {PLAN_TIERS}", name="plan_tier"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    # Always stored lower-cased (normalised in the schema layer) -> plain unique index.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(2), default="th", server_default="th")
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Bangkok", server_default="Asia/Bangkok"
    )
    theme: Mapped[str] = mapped_column(String(10), default="system", server_default="system")
    plan_tier: Mapped[str] = mapped_column(String(10), default="free", server_default="free")
    is_mentor: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
