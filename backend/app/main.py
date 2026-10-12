"""FastAPI application factory.

Run: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000`
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from app.core.config import Settings, get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.errors import register_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging
from app.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.diagnosis.router import router as mistake_categories_router
from app.modules.emotions.router import router as emotion_tags_router
from app.modules.symbols.router import router as symbols_router
from app.modules.users.router import router as users_router
from app.realtime.hub import Hub
from app.realtime.router import router as ws_router

API_PREFIX = "/api/v1"


def _api_router() -> APIRouter:
    api = APIRouter(prefix=API_PREFIX)
    for router in (
        health_router,
        auth_router,
        users_router,
        symbols_router,
        emotion_tags_router,
        mistake_categories_router,
        ws_router,
    ):
        api.include_router(router)
    return api


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings.DATABASE_URL)
        redis = Redis.from_url(settings.REDIS_URL, decode_responses=False)
        hub = Hub(redis)
        await hub.start()
        app.state.engine = engine
        app.state.sessionmaker = create_sessionmaker(engine)
        app.state.redis = redis
        app.state.hub = hub
        try:
            yield
        finally:
            await hub.stop()
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
        allow_credentials=True,  # refresh cookie
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)  # outermost: wraps CORS + routes
    register_error_handlers(app)
    app.include_router(_api_router())
    return app
