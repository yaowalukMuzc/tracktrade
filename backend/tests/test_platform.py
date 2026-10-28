"""Health, error envelope, request id, reference data endpoints, seeds."""

from __future__ import annotations

from decimal import Decimal

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.diagnosis.models import DIMENSIONS, MistakeCategory
from app.modules.emotions.models import EmotionTag
from app.modules.symbols.models import Symbol
from app.modules.users.models import User
from app.seeds import load_yaml, run_seeds
from tests.conftest import auth, signup

# ------------------------------------------------------------------ health / errors


async def test_health_ok(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


async def test_health_503_when_redis_down(client: httpx.AsyncClient, app: FastAPI) -> None:
    real = app.state.redis
    app.state.redis = Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2)
    try:
        res = await client.get("/api/v1/health")
    finally:
        await app.state.redis.aclose()
        app.state.redis = real
    assert res.status_code == 503
    body = res.json()
    assert body["code"] == "service_unavailable"
    assert body["details"]["db"] == "ok"
    assert body["details"]["redis"].startswith("error")


async def test_unknown_route_error_shape_and_request_id(client: httpx.AsyncClient) -> None:
    res = await client.get("/api/v1/nope", headers={"X-Request-ID": "req-123"})
    assert res.status_code == 404
    assert res.json() == {"code": "not_found", "message": "Not Found", "details": None}
    assert res.headers["x-request-id"] == "req-123"
    generated = await client.get("/api/v1/health")
    assert len(generated.headers["x-request-id"]) == 32


async def test_unhandled_exception_is_500_internal_error(app: FastAPI) -> None:
    async def boom() -> None:
        raise RuntimeError("kaboom")

    app.add_api_route("/__test/boom", boom)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.get("/__test/boom")
    assert res.status_code == 500
    assert res.json() == {
        "code": "internal_error",
        "message": "Internal server error",
        "details": None,
    }


# ------------------------------------------------------------------ reference data


async def test_reference_endpoints_require_auth(client: httpx.AsyncClient) -> None:
    for path in ("/api/v1/symbols", "/api/v1/emotion-tags", "/api/v1/mistake-categories"):
        assert (await client.get(path)).status_code == 401


async def test_symbols_endpoint(client: httpx.AsyncClient, app: FastAPI) -> None:
    headers = auth((await signup(app))["access_token"])
    symbols = {s["code"]: s for s in (await client.get("/api/v1/symbols", headers=headers)).json()}
    assert len(symbols) == len(load_yaml("symbols"))
    xau = symbols["XAUUSD"]
    assert xau["asset_class"] == "metal"
    assert xau["digits"] == 2
    # Decimals are serialised as strings.
    assert Decimal(xau["contract_size"]) == 100
    assert isinstance(xau["contract_size"], str)


async def test_emotion_tags_are_system_plus_own(
    client: httpx.AsyncClient, db: AsyncSession, app: FastAPI
) -> None:
    alice = await signup(app, "alice@example.com")
    bob = await signup(app, "bob@example.com")
    alice_user = (
        await db.execute(select(User).where(User.email == "alice@example.com"))
    ).scalar_one()
    db.add(
        EmotionTag(
            code="sleepy", label_th="ง่วง", label_en="Sleepy", valence="neg", user_id=alice_user.id
        )
    )
    await db.commit()

    a_tags = (await client.get("/api/v1/emotion-tags", headers=auth(alice["access_token"]))).json()
    b_tags = (await client.get("/api/v1/emotion-tags", headers=auth(bob["access_token"]))).json()
    system_count = len(load_yaml("emotion_tags"))
    assert len(a_tags) == system_count + 1
    assert len(b_tags) == system_count
    sleepy = next(t for t in a_tags if t["code"] == "sleepy")
    assert sleepy["is_system"] is False
    assert all(t["is_system"] for t in b_tags)
    assert {t["valence"] for t in b_tags} == {"pos", "neg", "neutral"}


async def test_mistake_categories_endpoint(client: httpx.AsyncClient, app: FastAPI) -> None:
    headers = auth((await signup(app))["access_token"])
    cats = (await client.get("/api/v1/mistake-categories", headers=headers)).json()
    assert [c["dimension"] for c in cats] == sorted(
        (c["dimension"] for c in cats), key=DIMENSIONS.index
    )
    assert {c["dimension"] for c in cats} == set(DIMENSIONS)


# ------------------------------------------------------------------ seeds


async def test_seeds_are_idempotent_and_specs_correct(db: AsyncSession) -> None:
    async def counts() -> tuple[int, int, int]:
        return (
            await db.scalar(select(func.count()).select_from(Symbol)) or 0,
            await db.scalar(
                select(func.count()).select_from(EmotionTag).where(EmotionTag.user_id.is_(None))
            )
            or 0,
            await db.scalar(select(func.count()).select_from(MistakeCategory)) or 0,
        )

    before = await counts()
    await run_seeds(db)
    await run_seeds(db)
    await db.commit()
    after = await counts()
    assert (
        before
        == after
        == (30, len(load_yaml("emotion_tags")), len(load_yaml("mistake_categories")))
    )

    specs = {s.code: s for s in (await db.execute(select(Symbol))).scalars()}
    expected = {
        # code: (asset_class, digits, point, pip, contract)
        "XAUUSD": ("metal", 2, "0.01", "0.1", "100"),
        "XAGUSD": ("metal", 3, "0.001", "0.01", "5000"),
        "EURUSD": ("fx", 5, "0.00001", "0.0001", "100000"),
        "GBPJPY": ("fx", 3, "0.001", "0.01", "100000"),
        "USDJPY": ("fx", 3, "0.001", "0.01", "100000"),
        "EURGBP": ("fx", 5, "0.00001", "0.0001", "100000"),
    }
    for code, (asset, digits, point, pip, contract) in expected.items():
        s = specs[code]
        assert (s.asset_class, s.digits) == (asset, digits), code
        assert (s.point_size, s.pip_size, s.contract_size) == (
            Decimal(point),
            Decimal(pip),
            Decimal(contract),
        ), code
    # Every JPY-quoted pair uses 3 digits, every other FX pair 5.
    for s in specs.values():
        if s.asset_class == "fx":
            assert s.digits == (3 if s.quote_currency == "JPY" else 5), s.code
            assert s.code == s.base_currency + s.quote_currency

    cats = (await db.execute(select(MistakeCategory))).scalars().all()
    per_dim = {d: sum(c.dimension == d for c in cats) for d in DIMENSIONS}
    assert all(2 <= n <= 5 for n in per_dim.values()), per_dim
    deviation_codes = {
        "entry_slippage",
        "sl_widened",
        "tp_moved",
        "oversize",
        "early_exit",
        "late_exit",
        "missed_partial",
        "missed_be",
        "unplanned",
    }
    assert deviation_codes <= {c.code for c in cats}
