"""`/auth/*` endpoints. All are rate limited per client IP + route."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import get_session
from app.core.ratelimit import rate_limit
from app.modules.auth import service
from app.modules.auth.schemas import AuthOut, LoginIn, RegisterIn, TokenOut
from app.modules.users.schemas import UserOut

REFRESH_COOKIE = "tt_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit("auth"))])


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _client(request: Request) -> service.ClientInfo:
    return service.ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )


def _set_refresh_cookie(
    response: Response, settings: Settings, tokens: service.IssuedTokens
) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        # remember=False -> browser-session cookie (no Max-Age); DB expiry is unchanged.
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 86400 if tokens.remember else None,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthOut:
    settings = _settings(request)
    tokens = await service.register(session, settings, body, _client(request))
    _set_refresh_cookie(response, settings, tokens)
    return AuthOut(user=UserOut.model_validate(tokens.user), access_token=tokens.access_token)


@router.post("/login", response_model=AuthOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> AuthOut:
    settings = _settings(request)
    tokens = await service.login(session, settings, body, _client(request))
    _set_refresh_cookie(response, settings, tokens)
    return AuthOut(user=UserOut.model_validate(tokens.user), access_token=tokens.access_token)


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    tt_refresh: str | None = Cookie(default=None),
) -> TokenOut:
    settings = _settings(request)
    tokens = await service.refresh(session, settings, tt_refresh, _client(request))
    _set_refresh_cookie(response, settings, tokens)
    return TokenOut(access_token=tokens.access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
    tt_refresh: str | None = Cookie(default=None),
) -> Response:
    await service.logout(session, tt_refresh)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response, _settings(request))
    return response
