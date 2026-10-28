"""Authentication dependencies (F-01 AC7): resolve the caller from a Better Auth JWT.

`Authorization: Bearer <jwt>` → signature/claims checked against the JWKS, then
the session (`sid`) must still exist and be unexpired in `auth_sessions` and
belong to `sub`. Signing out, revoking a device or resetting the password
deletes the session row, so the JWT stops working immediately (F-01 AC6).
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import Unauthorized
from app.core.logging import bind_user
from app.core.security import AccessClaims, InvalidToken, JwksProvider, decode_access_token
from app.modules.auth.models import AuthSession
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    claims: AccessClaims
    ctx: AccessContext


def _invalid() -> Unauthorized:
    return Unauthorized("invalid_token", "Session is invalid or expired")


async def _active_user(session: AsyncSession, claims: AccessClaims) -> User | None:
    stmt = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.id == claims.session_id,
            User.id == claims.user_id,
            AuthSession.expires_at > func.now(),
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def authenticate(
    token: str, *, settings: Settings, jwks: JwksProvider, session: AsyncSession
) -> CurrentUser:
    """Shared by HTTP requests and the WebSocket handshake. Raises Unauthorized."""
    try:
        claims = await decode_access_token(
            token, jwks=jwks, issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE
        )
    except InvalidToken as exc:
        raise _invalid() from exc
    user = await _active_user(session, claims)
    if user is None:
        raise _invalid()
    return CurrentUser(user=user, claims=claims, ctx=AccessContext(user_id=user.id))


async def get_current(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized()
    current = await authenticate(
        credentials.credentials,
        settings=request.app.state.settings,
        jwks=request.app.state.jwks,
        session=session,
    )
    bind_user(str(current.user.id))
    return current


async def get_current_user(current: CurrentUser = Depends(get_current)) -> User:
    return current.user


async def get_access_context(current: CurrentUser = Depends(get_current)) -> AccessContext:
    return current.ctx
