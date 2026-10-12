"""refresh_tokens table (spec §2.1 + PLAN M20: family, device info).

One row per issued refresh token. A *family* is the chain created by one login;
each refresh rotates to a new row in the same family. A family == one device
session (shown in `/me/sessions`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user_family", "user_id", "family_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when this token was exchanged for a newer one (rotation). Presenting a
    # rotated token again is a reuse signal -> revoke the whole family.
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Remember me": persistent cookie (Max-Age) vs browser-session cookie (PLAN M21).
    remember: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(64))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
