"""`/me` profile + sessions, including the F-01 AC4 ownership rule (404)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import NotFound
from app.modules.auth.models import RefreshToken
from app.modules.auth.router import REFRESH_COOKIE
from tests.conftest import PASSWORD, auth, refresh_with, register

ME = "/api/v1/me"
SESSIONS = "/api/v1/me/sessions"


async def test_me_requires_auth(client: httpx.AsyncClient) -> None:
    res = await client.get(ME)
    assert res.status_code == 401
    assert res.json() == {"code": "unauthorized", "message": "Not authenticated", "details": None}


async def test_get_and_patch_me(client: httpx.AsyncClient) -> None:
    body = await register(client)
    headers = auth(body["access_token"])

    me = await client.get(ME, headers=headers)
    assert me.status_code == 200
    assert me.json() == body["user"]

    res = await client.patch(
        ME,
        headers=headers,
        json={"locale": "en", "timezone": "Europe/London", "theme": "dark", "display_name": "N"},
    )
    assert res.status_code == 200, res.text
    user = res.json()
    assert (user["locale"], user["timezone"], user["theme"], user["display_name"]) == (
        "en",
        "Europe/London",
        "dark",
        "N",
    )
    assert (await client.get(ME, headers=headers)).json()["locale"] == "en"


async def test_patch_me_validation(client: httpx.AsyncClient) -> None:
    headers = auth((await register(client))["access_token"])
    bad_tz = await client.patch(ME, headers=headers, json={"timezone": "Bangkok/Nowhere"})
    assert bad_tz.status_code == 422
    assert bad_tz.json()["code"] == "validation_error"
    assert bad_tz.json()["details"][0]["loc"][-1] == "timezone"

    bad_locale = await client.patch(ME, headers=headers, json={"locale": "fr"})
    assert bad_locale.status_code == 422
    # Fields that are not user-editable are rejected outright.
    escalate = await client.patch(ME, headers=headers, json={"plan_tier": "pro"})
    assert escalate.status_code == 422


async def test_sessions_list_and_revoke(client: httpx.AsyncClient, app: FastAPI) -> None:
    reg = await register(client, "multi@example.com")
    # Second device = separate cookie jar.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as other:
        res = await other.post(
            "/api/v1/auth/login",
            json={"email": "multi@example.com", "password": PASSWORD},
            headers={"User-Agent": "PhoneBrowser/1.0"},
        )
        assert res.status_code == 200

        sessions = (await client.get(SESSIONS, headers=auth(reg["access_token"]))).json()
        assert len(sessions) == 2
        assert sum(s["current"] for s in sessions) == 1
        phone = next(s for s in sessions if s["user_agent"] == "PhoneBrowser/1.0")
        assert phone["current"] is False

        # Sign the phone out; its refresh token stops working.
        res = await client.delete(f"{SESSIONS}/{phone['id']}", headers=auth(reg["access_token"]))
        assert res.status_code == 204
        assert (await other.post("/api/v1/auth/refresh")).status_code == 401

    remaining = (await client.get(SESSIONS, headers=auth(reg["access_token"]))).json()
    assert [s["current"] for s in remaining] == [True]


async def test_cannot_revoke_another_users_session(client: httpx.AsyncClient) -> None:
    """F-01 AC4: user B deleting user A's session id -> 404, A's session untouched."""
    user_a = await register(client, "alice@example.com")
    a_cookie = client.cookies.get(REFRESH_COOKIE)
    a_sessions = (await client.get(SESSIONS, headers=auth(user_a["access_token"]))).json()
    a_session_id = a_sessions[0]["id"]

    client.cookies.clear()
    user_b = await register(client, "bob@example.com")

    res = await client.delete(f"{SESSIONS}/{a_session_id}", headers=auth(user_b["access_token"]))
    assert res.status_code == 404
    assert res.json()["code"] == "not_found"
    # Unknown id looks exactly the same.
    unknown = await client.delete(
        f"{SESSIONS}/{uuid.uuid4()}", headers=auth(user_b["access_token"])
    )
    assert unknown.status_code == 404
    assert unknown.json() == res.json()

    # B does not see A's session, and A's session still works.
    b_sessions = (await client.get(SESSIONS, headers=auth(user_b["access_token"]))).json()
    assert a_session_id not in {s["id"] for s in b_sessions}
    client.cookies.clear()
    assert a_cookie
    assert (await refresh_with(client, a_cookie)).status_code == 200


async def test_get_owned_or_404_filters_by_owner(client: httpx.AsyncClient, app: FastAPI) -> None:
    """The reusable owner-filter helper later modules use: foreign row == missing row."""
    alice = await register(client, "alice@example.com")
    client.cookies.clear()
    bob = await register(client, "bob@example.com")
    alice_id, bob_id = uuid.UUID(alice["user"]["id"]), uuid.UUID(bob["user"]["id"])

    async with app.state.sessionmaker() as session:
        token = (
            await session.execute(select(RefreshToken).where(RefreshToken.user_id == alice_id))
        ).scalar_one()
        owned = await get_owned_or_404(session, RefreshToken, token.id, AccessContext(alice_id))
        assert owned.id == token.id
        with pytest.raises(NotFound):
            await get_owned_or_404(session, RefreshToken, token.id, AccessContext(bob_id))
