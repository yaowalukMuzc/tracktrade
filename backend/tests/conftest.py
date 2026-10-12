"""Integration test fixtures: real Postgres + Redis.

Defaults match the local throwaway containers described in README:
  TEST_DATABASE_URL=postgresql+asyncpg://tracktrade:tracktrade@localhost:55432/tracktrade_test
  TEST_REDIS_URL=redis://localhost:56379/15

At session start the `public` schema is dropped and rebuilt with `alembic upgrade
head` (so migrations are exercised too) and reference data is seeded. Between
tests user-owned rows are deleted and the Redis DB is flushed.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from alembic.config import Config
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from alembic import command
from app.core.config import Settings
from app.main import create_app
from app.seeds import run_seeds

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracktrade:tracktrade@localhost:55432/tracktrade_test",
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:56379/15")
PASSWORD = "correct-horse-1"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "REDIS_URL": TEST_REDIS_URL,
        "JWT_SECRET": "test-secret-0123456789abcdef-0123456789",
        "CORS_ORIGINS": "http://localhost:5173",
        "COOKIE_SECURE": False,
        "RATE_LIMIT_AUTH": "1000/min",  # effectively off; the rate-limit test lowers it
        "LOG_LEVEL": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


async def _reset_schema() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


async def _seed() -> None:
    engine = create_async_engine(TEST_DATABASE_URL)
    async with AsyncSession(engine) as session, session.begin():
        await run_seeds(session)
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Fresh schema via Alembic migrations + seed data, once per test session."""
    asyncio.run(_reset_schema())
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    asyncio.run(_seed())


@pytest.fixture(scope="session")
def settings() -> Settings:
    return make_settings()


@pytest.fixture(scope="session")
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture(autouse=True)
async def _clean(app: FastAPI) -> AsyncIterator[None]:
    """Remove user data (cascades to tokens/custom tags) and Redis keys."""
    async with app.state.engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))
    await app.state.redis.flushdb()
    yield


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.sessionmaker() as session:
        yield session


# ---------------------------------------------------------------- helpers


def register_payload(email: str = "a@example.com", **overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "password": PASSWORD,
        "display_name": "Nook",
        "locale": "th",
        "timezone": "Asia/Bangkok",
        "accept_terms": True,
    }
    payload.update(overrides)
    return payload


async def register(client: httpx.AsyncClient, email: str = "a@example.com") -> dict[str, Any]:
    res = await client.post("/api/v1/auth/register", json=register_payload(email))
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def refresh_with(client: httpx.AsyncClient, refresh_token: str) -> httpx.Response:
    """POST /auth/refresh presenting exactly this refresh token (jar cleared first)."""
    client.cookies.clear()
    return await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"tt_refresh={refresh_token}"}
    )
