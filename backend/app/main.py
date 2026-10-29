"""FastAPI application factory.

Run: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.core.security import JwksProvider, RemoteJwks
from app.core.storage import LocalStorage, Storage
from app.health import router as health_router
from app.modules.accounts.router import router as accounts_router
from app.modules.analysis.router import router as analysis_router
from app.modules.attachments.router import router as attachments_router
from app.modules.auth.deps import get_current
from app.modules.connections.router import ingest_router
from app.modules.connections.router import public_router as connections_public
from app.modules.connections.router import router as connections_router
from app.modules.diagnosis.router import router as mistake_categories_router
from app.modules.emotions.router import router as emotion_tags_router
from app.modules.plans.router import router as plans_router
from app.modules.playbook.router import router as setups_router
from app.modules.positions.router import router as positions_router
from app.modules.risk.router import router as risk_router
from app.modules.symbols.router import router as symbols_router
from app.modules.today.router import router as today_router
from app.modules.users.router import router as users_router
from app.realtime.hub import Hub
from app.realtime.router import router as ws_router

API_PREFIX = "/api/v1"


# Every HTTP router here requires a valid Better Auth session (F-01 AC7). The only public
# HTTP route is /health; sign-in/up/reset live in the auth service under /api/auth/*.
# The WebSocket authenticates its own handshake (`?token=`), `/ingest` its API key and the
# cTrader OAuth callback its signed `state`.
PROTECTED_ROUTERS = (
    users_router,
    symbols_router,
    emotion_tags_router,
    mistake_categories_router,
    accounts_router,
    risk_router,
    setups_router,
    attachments_router,
    analysis_router,
    plans_router,
    positions_router,
    connections_router,
    today_router,
)


def _api_router() -> APIRouter:
    api = APIRouter(prefix=API_PREFIX)
    api.include_router(health_router)
    for router in PROTECTED_ROUTERS:
        api.include_router(router, dependencies=[Depends(get_current)])
    api.include_router(ws_router)
    # The MT5 EA authenticates with its per-account API key, not a user session.
    api.include_router(ingest_router)
    api.include_router(connections_public)  # cTrader OAuth callback (signed state)
    return api


def create_app(
    settings: Settings | None = None,
    *,
    jwks: JwksProvider | None = None,
    storage: Storage | None = None,
) -> FastAPI:
    """`jwks` / `storage` override the remote key set and the file store (tests)."""
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.DATABASE_URL)
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        hub = Hub(redis)
        await hub.start()
        queue = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = redis
        app.state.queue = queue  # arq: background jobs (recompute, cTrader sync, …)
        app.state.hub = hub
        app.state.jwks = jwks or RemoteJwks(settings.AUTH_JWKS_URL, ttl=settings.JWKS_CACHE_SEC)
        app.state.storage = storage or LocalStorage(settings.MEDIA_ROOT)
        try:
            yield
        finally:
            await app.state.jwks.aclose()
            await hub.stop()
            await queue.aclose()
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(
        title="TrackTrade API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if settings.ENV != "prod" else None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.ENV != "prod" else None,
    )
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,  # bearer JWT only; auth cookies belong to /api/auth
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)  # outermost: wraps CORS + routes
    register_error_handlers(app)
    app.include_router(_api_router())
    return app
