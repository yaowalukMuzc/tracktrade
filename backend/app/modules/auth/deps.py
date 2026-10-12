"""Authentication dependencies: resolve the caller from `Authorization: Bearer`."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings
from app.core.db import get_session
from app.core.errors import Unauthorized
from app.core.logging import bind_user
from app.core.security import AccessClaims, InvalidToken, decode_access_token
from app.modules.users.models import User

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user: User
    claims: AccessClaims
    ctx: AccessContext


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


async def get_current(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise Unauthorized()
    try:
        claims = decode_access_token(credentials.credentials, secret=_settings(request).JWT_SECRET)
    except InvalidToken as exc:
        raise Unauthorized("invalid_token", "Access token is invalid or expired") from exc
    user = await session.get(User, claims.user_id)
    if user is None:
        raise Unauthorized("invalid_token", "Access token is invalid or expired")
    bind_user(str(user.id))
    return CurrentUser(user=user, claims=claims, ctx=AccessContext(user_id=user.id))


async def get_current_user(current: CurrentUser = Depends(get_current)) -> User:
    return current.user


async def get_access_context(current: CurrentUser = Depends(get_current)) -> AccessContext:
    return current.ctx
