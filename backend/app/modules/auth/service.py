"""Auth business rules (F-01): register, login, refresh rotation, logout, sessions.

Refresh tokens are opaque random strings; only sha256(token) is stored. Every
use rotates the token (old row gets `rotated_at`, a new row joins the same
family). Presenting a token that was already rotated means it leaked or was
replayed, so the whole family is revoked (`token_reused`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings
from app.core.errors import Conflict, NotFound, Unauthorized
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.modules.auth import repo
from app.modules.auth.models import RefreshToken
from app.modules.auth.schemas import LoginIn, RegisterIn
from app.modules.users import repo as users_repo
from app.modules.users.models import User
from app.modules.users.schemas import SessionOut


@dataclass(frozen=True, slots=True)
class ClientInfo:
    user_agent: str | None
    ip: str | None


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    user: User
    access_token: str
    refresh_token: str
    remember: bool


def _now() -> datetime:
    return datetime.now(UTC)


def _access_token(settings: Settings, user_id: uuid.UUID, family_id: uuid.UUID) -> str:
    return create_access_token(
        user_id,
        secret=settings.JWT_SECRET,
        ttl=timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN),
        session_id=family_id,
    )


async def _issue(
    session: AsyncSession,
    settings: Settings,
    user: User,
    client: ClientInfo,
    *,
    family_id: uuid.UUID | None = None,
    remember: bool = True,
    now: datetime | None = None,
) -> IssuedTokens:
    now = now or _now()
    raw = new_refresh_token()
    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        family_id=family_id or uuid.uuid4(),
        # DB expiry is always the full refresh TTL; `remember` only affects the cookie.
        expires_at=now + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        remember=remember,
        user_agent=(client.user_agent or "")[:512] or None,
        ip=client.ip,
        last_used_at=now,
    )
    session.add(token)
    await session.flush()
    return IssuedTokens(
        user=user,
        access_token=_access_token(settings, user.id, token.family_id),
        refresh_token=raw,
        remember=remember,
    )


async def register(
    session: AsyncSession, settings: Settings, body: RegisterIn, client: ClientInfo
) -> IssuedTokens:
    if await users_repo.get_by_email(session, body.email) is not None:
        raise Conflict("email_taken", "An account with this email already exists")
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
        locale=body.locale,
        timezone=body.timezone,
    )
    try:
        await users_repo.add(session, user)
    except IntegrityError as exc:  # concurrent registration with the same email
        raise Conflict("email_taken", "An account with this email already exists") from exc
    await session.refresh(user)
    return await _issue(session, settings, user, client)


async def login(
    session: AsyncSession, settings: Settings, body: LoginIn, client: ClientInfo
) -> IssuedTokens:
    user = await users_repo.get_by_email(session, body.email)
    # verify_password runs a dummy hash for unknown users to keep timing uniform.
    if not verify_password(user.password_hash if user else None, body.password) or user is None:
        raise Unauthorized("invalid_credentials", "Email or password is incorrect")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    return await _issue(session, settings, user, client, remember=body.remember)


def _lost_response(
    settings: Settings, token: RefreshToken, head: RefreshToken | None, now: datetime
) -> bool:
    """True when a rotated token is replayed because its refresh response never arrived.

    Only the newest rotation qualifies (`head` was issued by rotating `token`) and only within
    REFRESH_REUSE_GRACE_SEC; replaying any older token is still treated as theft.
    """
    if head is None or token.rotated_at is None:
        return False
    within_grace = now - token.rotated_at <= timedelta(seconds=settings.REFRESH_REUSE_GRACE_SEC)
    # A rotation stamps the child's last_used_at with the parent's rotated_at (see `refresh`).
    return within_grace and head.last_used_at == token.rotated_at


async def refresh(
    session: AsyncSession, settings: Settings, raw_token: str | None, client: ClientInfo
) -> IssuedTokens:
    invalid = Unauthorized("invalid_refresh_token", "Refresh token is missing or invalid")
    if not raw_token:
        raise invalid
    now = _now()
    token = await repo.get_by_hash_for_update(session, hash_refresh_token(raw_token))
    if token is None or token.revoked_at is not None:
        raise invalid
    if token.rotated_at is not None:
        head = await repo.family_head_for_update(session, token.family_id)
        if not _lost_response(settings, token, head, now):
            # Replay of an already-rotated token: kill the whole session family and
            # persist that even though the request fails.
            await repo.revoke_family(session, token.family_id, now)
            await session.commit()
            raise Unauthorized("token_reused", "Refresh token reuse detected; session revoked")
        # The client never received `head` (its refresh response was aborted), so retire
        # that unseen token and continue the family from here instead of logging out.
        assert head is not None
        head.revoked_at = now
    if token.expires_at <= now:
        raise Unauthorized("refresh_expired", "Session expired, please sign in again")

    user = await session.get(User, token.user_id)
    if user is None:
        raise invalid
    token.rotated_at = now
    token.last_used_at = now
    return await _issue(
        session,
        settings,
        user,
        ClientInfo(user_agent=client.user_agent or token.user_agent, ip=client.ip or token.ip),
        family_id=token.family_id,
        remember=token.remember,
        now=now,  # links the child to this rotation for the lost-response check
    )


async def logout(session: AsyncSession, raw_token: str | None) -> None:
    """Revoke the session family of the presented refresh token (idempotent)."""
    if not raw_token:
        return
    token = await repo.get_by_hash_for_update(session, hash_refresh_token(raw_token))
    if token is not None:
        await repo.revoke_family(session, token.family_id, _now())


async def list_sessions(
    session: AsyncSession, ctx: AccessContext, *, current_session_id: uuid.UUID | None
) -> list[SessionOut]:
    rows = await repo.active_heads(session, ctx, _now())
    return [
        SessionOut(
            id=token.family_id,
            user_agent=token.user_agent,
            ip=token.ip,
            created_at=started_at,
            last_used_at=token.last_used_at,
            expires_at=token.expires_at,
            current=token.family_id == current_session_id,
        )
        for token, started_at in rows
    ]


async def revoke_session(session: AsyncSession, ctx: AccessContext, family_id: uuid.UUID) -> None:
    """Sign out one device. Someone else's (or unknown) session id -> 404."""
    now = _now()
    if not await repo.owned_family_exists(session, ctx, family_id, now):
        raise NotFound("Session not found")
    await repo.revoke_family(session, family_id, now, user_id=ctx.owner_id)
