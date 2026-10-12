"""F-01: register / login / refresh rotation + reuse detection / logout / rate limit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import RefreshToken
from app.modules.auth.router import REFRESH_COOKIE
from tests.conftest import PASSWORD, auth, refresh_with, register, register_payload

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


def _assert_error(res: httpx.Response, status: int, code: str) -> dict:
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"code", "message", "details"}
    assert body["code"] == code
    return body


# ------------------------------------------------------------------ register


async def test_register_returns_user_token_and_cookie(client: httpx.AsyncClient) -> None:
    res = await client.post(REGISTER, json=register_payload("New.User@Example.com"))
    assert res.status_code == 201
    body = res.json()
    assert set(body["user"]) == {
        "id",
        "email",
        "display_name",
        "locale",
        "timezone",
        "theme",
        "plan_tier",
        "is_mentor",
    }
    assert body["user"]["email"] == "new.user@example.com"  # normalised
    assert body["user"]["theme"] == "system"
    assert body["user"]["plan_tier"] == "free"
    assert body["access_token"]

    cookie = res.headers["set-cookie"]
    assert cookie.startswith(f"{REFRESH_COOKIE}=")
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=strict" in lowered
    assert "path=/api/v1/auth" in lowered
    assert "secure" not in lowered  # COOKIE_SECURE=false in tests


async def test_register_password_too_short_is_422(client: httpx.AsyncClient) -> None:
    res = await client.post(REGISTER, json=register_payload(password="1234567"))
    body = _assert_error(res, 422, "validation_error")
    assert any(err["loc"][-1] == "password" for err in body["details"])


async def test_register_requires_accept_terms(client: httpx.AsyncClient) -> None:
    res = await client.post(REGISTER, json=register_payload(accept_terms=False))
    body = _assert_error(res, 422, "validation_error")
    assert any(err["loc"][-1] == "accept_terms" for err in body["details"])


async def test_register_duplicate_email_is_409(client: httpx.AsyncClient) -> None:
    await register(client, "dup@example.com")
    res = await client.post(REGISTER, json=register_payload("DUP@example.com"))
    _assert_error(res, 409, "email_taken")


async def test_register_rejects_invalid_timezone(client: httpx.AsyncClient) -> None:
    res = await client.post(REGISTER, json=register_payload(timezone="Mars/Olympus"))
    _assert_error(res, 422, "validation_error")


# ------------------------------------------------------------------ login


async def test_login_ok_and_bad_credentials(client: httpx.AsyncClient) -> None:
    await register(client, "login@example.com")
    ok = await client.post(LOGIN, json={"email": "LOGIN@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == "login@example.com"
    assert ok.json()["access_token"]

    bad = await client.post(LOGIN, json={"email": "login@example.com", "password": "nope-nope"})
    _assert_error(bad, 401, "invalid_credentials")
    unknown = await client.post(LOGIN, json={"email": "ghost@example.com", "password": PASSWORD})
    _assert_error(unknown, 401, "invalid_credentials")


async def test_token_lifetimes(client: httpx.AsyncClient, app: FastAPI, db: AsyncSession) -> None:
    """Access token = 15 min (HS256, sub, type=access); refresh = 30 days."""
    settings = app.state.settings
    assert settings.ACCESS_TOKEN_TTL_MIN == 15
    assert settings.REFRESH_TOKEN_TTL_DAYS == 30

    body = await register(client, "ttl@example.com")
    claims = jwt.decode(body["access_token"], settings.JWT_SECRET, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert claims["sub"] == body["user"]["id"]
    assert claims["type"] == "access"

    res = await client.post(LOGIN, json={"email": "ttl@example.com", "password": PASSWORD})
    assert f"max-age={30 * 86400}" in res.headers["set-cookie"].lower()

    token = (await db.execute(select(RefreshToken).limit(1))).scalar_one()
    delta = token.expires_at - datetime.now(UTC)
    assert timedelta(days=29, hours=23) < delta <= timedelta(days=30)
    # Only the sha256 hash is stored, never the raw token.
    assert len(token.token_hash) == 64
    assert client.cookies.get(REFRESH_COOKIE) != token.token_hash


async def test_login_without_remember_sets_session_cookie(client: httpx.AsyncClient) -> None:
    await register(client, "nomem@example.com")
    res = await client.post(
        LOGIN, json={"email": "nomem@example.com", "password": PASSWORD, "remember": False}
    )
    assert res.status_code == 200
    assert "max-age" not in res.headers["set-cookie"].lower()
    # Rotation keeps it a session cookie.
    refreshed = await client.post(REFRESH)
    assert refreshed.status_code == 200
    assert "max-age" not in refreshed.headers["set-cookie"].lower()


async def test_expired_access_token_is_rejected(client: httpx.AsyncClient, app: FastAPI) -> None:
    body = await register(client, "exp@example.com")
    expired = jwt.encode(
        {
            "sub": body["user"]["id"],
            "type": "access",
            "iat": int((datetime.now(UTC) - timedelta(minutes=30)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(minutes=15)).timestamp()),
        },
        app.state.settings.JWT_SECRET,
        algorithm="HS256",
    )
    res = await client.get("/api/v1/me", headers=auth(expired))
    _assert_error(res, 401, "invalid_token")


# ------------------------------------------------------------------ refresh / logout


async def _age_rotation(db: AsyncSession, raw_token: str, seconds: int) -> None:
    """Pretend `raw_token` was rotated `seconds` ago (pushes it out of the reuse grace window)."""
    from app.core.security import hash_refresh_token

    row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
    ).scalar_one()
    assert row.rotated_at is not None
    row.rotated_at -= timedelta(seconds=seconds)
    await db.commit()


async def test_refresh_rotates_and_reuse_revokes_family(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await register(client, "rot@example.com")
    first = client.cookies.get(REFRESH_COOKIE)
    assert first

    res = await client.post(REFRESH)
    assert res.status_code == 200
    assert res.json()["access_token"]
    second = client.cookies.get(REFRESH_COOKIE)
    assert second and second != first

    # Replaying the already-rotated token after the grace window -> 401 token_reused ...
    await _age_rotation(db, first, 120)
    reused = await refresh_with(client, first)
    _assert_error(reused, 401, "token_reused")

    # ... and the whole family is dead, including the newest token.
    after = await refresh_with(client, second)
    _assert_error(after, 401, "invalid_refresh_token")


async def test_replay_of_just_rotated_token_recovers_lost_response(
    client: httpx.AsyncClient,
) -> None:
    """A reload can abort the refresh response, so the browser re-sends the token it still has."""
    await register(client, "lost@example.com")
    first = client.cookies.get(REFRESH_COOKIE)
    assert first
    assert (await client.post(REFRESH)).status_code == 200
    unseen = client.cookies.get(REFRESH_COOKIE)  # the response the browser never stored
    assert unseen

    recovered = await refresh_with(client, first)
    assert recovered.status_code == 200, recovered.text
    third = client.cookies.get(REFRESH_COOKIE)
    assert third and third not in (first, unseen)

    # The unseen successor is retired; the new chain keeps working.
    _assert_error(await refresh_with(client, unseen), 401, "invalid_refresh_token")
    assert (await refresh_with(client, third)).status_code == 200


async def test_replay_of_older_token_is_theft_even_within_grace(client: httpx.AsyncClient) -> None:
    await register(client, "old@example.com")
    first = client.cookies.get(REFRESH_COOKIE)
    assert first
    assert (await client.post(REFRESH)).status_code == 200
    assert (await client.post(REFRESH)).status_code == 200
    latest = client.cookies.get(REFRESH_COOKIE)
    assert latest

    # `first` is two rotations old: only the newest rotation gets the grace.
    _assert_error(await refresh_with(client, first), 401, "token_reused")
    _assert_error(await refresh_with(client, latest), 401, "invalid_refresh_token")


async def test_refresh_without_cookie_is_401(client: httpx.AsyncClient) -> None:
    res = await client.post(REFRESH)
    _assert_error(res, 401, "invalid_refresh_token")


async def test_logout_revokes_and_clears_cookie(client: httpx.AsyncClient) -> None:
    await register(client, "out@example.com")
    token = client.cookies.get(REFRESH_COOKIE)
    assert token

    res = await client.post(LOGOUT)
    assert res.status_code == 204
    set_cookie = res.headers["set-cookie"].lower()
    assert set_cookie.startswith(f"{REFRESH_COOKIE}=") and "max-age=0" in set_cookie
    assert client.cookies.get(REFRESH_COOKIE) is None

    again = await refresh_with(client, token)
    _assert_error(again, 401, "invalid_refresh_token")


# ------------------------------------------------------------------ rate limit


async def test_auth_rate_limit_returns_429(client: httpx.AsyncClient, app: FastAPI) -> None:
    original = app.state.settings
    app.state.settings = original.model_copy(update={"RATE_LIMIT_AUTH": "3/min"})
    try:
        payload = {"email": "rl@example.com", "password": "whatever-123"}
        codes = [(await client.post(LOGIN, json=payload)).status_code for _ in range(3)]
        assert codes == [401, 401, 401]
        limited = await client.post(LOGIN, json=payload)
        body = _assert_error(limited, 429, "rate_limited")
        assert body["details"]["retry_after"] >= 1
        assert int(limited.headers["retry-after"]) >= 1
        # Keyed per route: another auth route still has its own budget.
        assert (await client.post(REFRESH)).status_code == 401
    finally:
        app.state.settings = original
