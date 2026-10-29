"""cTrader OAuth 2 (authorization code) — authorize URL, code exchange, refresh.

The `state` round-trips the trader + account through cTrader: it is Fernet-sealed (encrypted +
authenticated) and carries a one-time nonce kept in Redis for 10 minutes, so a callback can't be
forged or replayed.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.core.crypto import SecretBox
from app.core.errors import AppError
from app.modules.connections.ctrader.client import CTraderError

STATE_TTL_S = 600
NONCE_KEY = "ctrader:oauth:{}"


@dataclass(frozen=True, slots=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def sealed(self, box: SecretBox) -> str:
        return box.seal(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at.isoformat(),
            }
        )

    @classmethod
    def unsealed(cls, box: SecretBox, value: str) -> Tokens:
        data = box.open(value)
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


def configured(settings: Settings) -> bool:
    return bool(
        settings.CTRADER_CLIENT_ID and settings.CTRADER_CLIENT_SECRET and settings.FERNET_KEY
    )


def require_configured(settings: Settings) -> SecretBox:
    if not configured(settings):
        raise AppError(
            "ctrader_not_configured",
            "cTrader linking is not set up on this server",
            status_code=503,
        )
    return SecretBox(settings.FERNET_KEY)


async def new_state(redis: Redis, box: SecretBox, user_id: uuid.UUID, account_id: uuid.UUID) -> str:
    nonce = secrets.token_urlsafe(16)
    await redis.set(NONCE_KEY.format(nonce), str(account_id), ex=STATE_TTL_S)
    return box.seal({"u": str(user_id), "a": str(account_id), "n": nonce})


async def read_state(redis: Redis, box: SecretBox, state: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Validate + consume. Raises AppError('invalid_state')."""
    try:
        data = box.open(state)
        nonce = str(data["n"])
        user_id, account_id = uuid.UUID(data["u"]), uuid.UUID(data["a"])
    except (AppError, KeyError, ValueError) as exc:
        raise AppError("invalid_state", "The link has expired, try again", status_code=400) from exc
    stored = await redis.getdel(NONCE_KEY.format(nonce))
    if stored is None or (stored.decode() if isinstance(stored, bytes) else stored) != str(
        account_id
    ):
        raise AppError("invalid_state", "The link has expired, try again", status_code=400)
    return user_id, account_id


def authorize_url(settings: Settings, state: str) -> str:
    query = urlencode(
        {
            "client_id": settings.CTRADER_CLIENT_ID,
            "redirect_uri": settings.CTRADER_REDIRECT_URI,
            "scope": "trading",
            "product": "web",
            "state": state,
        }
    )
    return f"{settings.CTRADER_AUTH_URL}?{query}"


def _tokens(body: dict[str, Any]) -> Tokens:
    if body.get("errorCode") or not body.get("accessToken"):
        raise CTraderError(
            str(body.get("errorCode") or "invalid_grant"), str(body.get("description", ""))
        )
    return Tokens(
        access_token=str(body["accessToken"]),
        refresh_token=str(body.get("refreshToken", "")),
        expires_at=datetime.now(UTC) + timedelta(seconds=int(body.get("expiresIn", 2_628_000))),
    )


async def exchange_code(settings: Settings, http: httpx.AsyncClient, code: str) -> Tokens:
    res = await http.get(
        settings.CTRADER_TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.CTRADER_REDIRECT_URI,
            "client_id": settings.CTRADER_CLIENT_ID,
            "client_secret": settings.CTRADER_CLIENT_SECRET,
        },
        timeout=20,
    )
    return _tokens(res.json())


async def refresh(settings: Settings, http: httpx.AsyncClient, refresh_token: str) -> Tokens:
    res = await http.get(
        settings.CTRADER_TOKEN_URL,
        params={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.CTRADER_CLIENT_ID,
            "client_secret": settings.CTRADER_CLIENT_SECRET,
        },
        timeout=20,
    )
    return _tokens(res.json())
