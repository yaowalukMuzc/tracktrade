"""Integration test fixtures: real Postgres + Redis.

Defaults match the local throwaway containers described in README:
  TEST_DATABASE_URL=postgresql+asyncpg://tracktrade:tracktrade@localhost:55432/tracktrade_test
  TEST_REDIS_URL=redis://localhost:56379/15

At session start the `public` schema is dropped and rebuilt with `alembic upgrade
head` (so migrations are exercised too) and reference data is seeded. Between
tests user-owned rows are deleted and the Redis DB is flushed.

Auth: the app trusts a test Ed25519 key (`TEST_JWKS`). `signup()` inserts a user +
Better Auth session row directly and mints the same JWT shape the auth service
issues (`sub`, `sid`, `iss`, `aud`, 15 min). The auth service itself is tested in
`auth/test`.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alembic import command
from app.core.config import Settings
from app.core.security import StaticJwks
from app.core.storage import LocalStorage
from app.main import create_app
from app.modules.auth.models import AuthSession
from app.modules.users.models import User
from app.modules.users.schemas import UserOut
from app.seeds import run_seeds

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://tracktrade:tracktrade@localhost:55432/tracktrade_test",
)
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:56379/15")

TEST_KID = "test-key-1"
TEST_SIGNING_KEY = Ed25519PrivateKey.generate()
TEST_JWKS = {
    "keys": [
        {
            **json.loads(jwt.algorithms.OKPAlgorithm.to_jwk(TEST_SIGNING_KEY.public_key())),
            "kid": TEST_KID,
            "alg": "EdDSA",
        }
    ]
}
ISSUER, AUDIENCE = "tracktrade-auth", "tracktrade-api"


def make_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "ENV": "test",
        "DATABASE_URL": TEST_DATABASE_URL,
        "REDIS_URL": TEST_REDIS_URL,
        "AUTH_JWKS_URL": "http://auth.invalid/api/auth/jwks",
        "JWT_ISSUER": ISSUER,
        "JWT_AUDIENCE": AUDIENCE,
        "CORS_ORIGINS": "http://localhost:5178",
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


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    """Fresh schema via Alembic migrations + seed data, once per test session."""
    asyncio.run(_reset_schema())
    command.upgrade(alembic_config(), "head")
    asyncio.run(_seed())


@pytest.fixture(scope="session")
def settings() -> Settings:
    return make_settings()


@pytest.fixture(scope="session")
async def app(
    settings: Settings, tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[FastAPI]:
    storage = LocalStorage(tmp_path_factory.mktemp("media"))
    application = create_app(settings, jwks=StaticJwks(TEST_JWKS), storage=storage)
    async with application.router.lifespan_context(application):
        yield application


@pytest.fixture(autouse=True)
async def _clean(app: FastAPI) -> AsyncIterator[None]:
    """Remove user data (cascades to sessions/accounts/custom tags) and Redis keys."""
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


def mint_token(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    *,
    key: Ed25519PrivateKey = TEST_SIGNING_KEY,
    kid: str = TEST_KID,
    ttl: timedelta = timedelta(minutes=15),
    **claims: Any,
) -> str:
    """A JWT shaped like the Better Auth jwt plugin's (EdDSA, kid, sub, sid, iss, aud)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    payload.update(claims)
    return jwt.encode(payload, key, algorithm="EdDSA", headers={"kid": kid})


async def signup(
    app: FastAPI,
    email: str = "a@example.com",
    *,
    display_name: str = "Nook",
    locale: str = "th",
    timezone: str = "Asia/Bangkok",
) -> dict[str, Any]:
    """User + one live session, like Better Auth sign-up -> {user, access_token, session_id}."""
    sessionmaker: async_sessionmaker[AsyncSession] = app.state.sessionmaker
    async with sessionmaker() as db, db.begin():
        user = User(email=email, display_name=display_name, locale=locale, timezone=timezone)
        db.add(user)
        await db.flush()
        auth_session = AuthSession(
            user_id=user.id,
            token=uuid.uuid4().hex,
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        db.add(auth_session)
        await db.flush()
        await db.refresh(user)
        out = UserOut.model_validate(user).model_dump(mode="json")
        session_id = auth_session.id
    token = mint_token(out["id"], session_id)
    return {"user": out, "access_token": token, "session_id": session_id}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
