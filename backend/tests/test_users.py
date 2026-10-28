"""`/me` profile, and the F-01 AC4 ownership rule (404)."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import NotFound
from app.modules.auth.models import AuthSession
from tests.conftest import auth, signup

ME = "/api/v1/me"


async def test_me_requires_auth(client: httpx.AsyncClient) -> None:
    res = await client.get(ME)
    assert res.status_code == 401
    assert res.json() == {"code": "unauthorized", "message": "Not authenticated", "details": None}


async def test_get_and_patch_me(client: httpx.AsyncClient, app: FastAPI) -> None:
    body = await signup(app)
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


async def test_patch_me_validation(client: httpx.AsyncClient, app: FastAPI) -> None:
    headers = auth((await signup(app))["access_token"])
    bad_tz = await client.patch(ME, headers=headers, json={"timezone": "Bangkok/Nowhere"})
    assert bad_tz.status_code == 422
    assert bad_tz.json()["code"] == "validation_error"
    assert bad_tz.json()["details"][0]["loc"][-1] == "timezone"

    bad_locale = await client.patch(ME, headers=headers, json={"locale": "fr"})
    assert bad_locale.status_code == 422
    # Fields that are not user-editable are rejected outright.
    escalate = await client.patch(ME, headers=headers, json={"plan_tier": "pro"})
    assert escalate.status_code == 422


async def test_get_owned_or_404_filters_by_owner(app: FastAPI) -> None:
    """The reusable owner-filter helper every module uses: foreign row == missing row."""
    alice = await signup(app, "alice@example.com")
    bob = await signup(app, "bob@example.com")
    alice_id, bob_id = uuid.UUID(alice["user"]["id"]), uuid.UUID(bob["user"]["id"])

    async with app.state.sessionmaker() as session:
        row = (
            await session.execute(select(AuthSession).where(AuthSession.user_id == alice_id))
        ).scalar_one()
        owned = await get_owned_or_404(session, AuthSession, row.id, AccessContext(alice_id))
        assert owned.id == row.id
        with pytest.raises(NotFound):
            await get_owned_or_404(session, AuthSession, row.id, AccessContext(bob_id))
        with pytest.raises(NotFound):
            await get_owned_or_404(session, AuthSession, uuid.uuid4(), AccessContext(alice_id))
