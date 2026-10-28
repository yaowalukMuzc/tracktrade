"""Better Auth tables (spec §2.1, PLAN §5.3).

The Better Auth service (`auth/`) reads and writes these tables; Alembic owns the
schema so there is a single migration history. Column names are the snake_case
`fields` mapping configured in `auth/src/auth.ts` — keep both in sync.

FastAPI only reads `auth_sessions` (is the session behind a JWT still alive?).
Ids default to `gen_random_uuid()` because Better Auth (`generateId: "uuid"`)
lets Postgres generate them.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base


class _AuthBase(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )


class AuthSession(_AuthBase):
    __tablename__ = "auth_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip_address: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)


class AuthAccount(_AuthBase):
    """Login method of a user. Email/password = `provider_id='credential'` (+ argon2 `password`)."""

    __tablename__ = "auth_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[str] = mapped_column(Text)
    access_token: Mapped[str | None] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    id_token: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str | None] = mapped_column(Text)
    password: Mapped[str | None] = mapped_column(Text)


class AuthVerification(_AuthBase):
    """One-time tokens (password reset). Deleted by Better Auth when used."""

    __tablename__ = "auth_verifications"

    identifier: Mapped[str] = mapped_column(Text, index=True)
    value: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuthJwk(_AuthBase):
    """Signing keys of the JWT plugin (private key encrypted with BETTER_AUTH_SECRET)."""

    __tablename__ = "auth_jwks"

    public_key: Mapped[str] = mapped_column(Text)
    private_key: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alg: Mapped[str | None] = mapped_column(Text)
    crv: Mapped[str | None] = mapped_column(Text)
