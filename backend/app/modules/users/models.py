"""users table (spec §2.1 + PLAN M19 `theme`).

Shared with the Better Auth service, which creates users and maps its `name`
field to `display_name` (PLAN §5.3). Passwords live in `auth_accounts`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, String, Text, text
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

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    # Always stored lower-cased (Better Auth normalises) -> plain unique index.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    image: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(100))
    locale: Mapped[str] = mapped_column(String(2), default="th", server_default="th")
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Bangkok", server_default="Asia/Bangkok"
    )
    theme: Mapped[str] = mapped_column(String(10), default="system", server_default="system")
    plan_tier: Mapped[str] = mapped_column(String(10), default="free", server_default="free")
    is_mentor: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
