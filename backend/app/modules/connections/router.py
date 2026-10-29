"""Connections (signed-in user) and `/ingest` (EA, API key) — F-08."""

from __future__ import annotations

import asyncio
import io
import json
import uuid
import zipfile
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings, parse_rate
from app.core.db import get_session
from app.core.effects import Effects, get_effects
from app.core.errors import AppError, NotFound
from app.core.ratelimit import RateLimited, hit
from app.modules.accounts import service as accounts_service
from app.modules.auth.deps import get_access_context
from app.modules.connections import ingest, service
from app.modules.connections.ctrader import oauth
from app.modules.connections.ctrader.client import CTraderError
from app.modules.connections.schemas import (
    ApiKeyOut,
    AuthorizeOut,
    ConnectionOut,
    IngestIn,
    IngestionJobOut,
    IngestOut,
)

router = APIRouter(tags=["connections"])
ingest_router = APIRouter(tags=["ingest"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)
Fx = Depends(get_effects)


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


Conf = Depends(_settings)


@router.get("/accounts/{account_id}/connections", response_model=list[ConnectionOut])
async def list_connections(
    account_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> list[ConnectionOut]:
    """Status, last sync, last error and today's counts (F-08 AC6)."""
    return await service.list_connections(session, ctx, settings, account_id)


@router.post(
    "/accounts/{account_id}/connections/mt5",
    response_model=ApiKeyOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_mt5_key(
    account_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> ApiKeyOut:
    """Create (or rotate) the EA's API key. The full key is in this response only."""
    conn, key = await service.create_mt5_key(session, ctx, settings, account_id)
    return ApiKeyOut(connection=await service.to_out(session, ctx, settings, conn), api_key=key)


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(
    connection_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    await service.disconnect(session, ctx, connection_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/connections/{connection_id}/sync",
    response_model=ConnectionOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_now(
    connection_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    fx: Effects = Fx,
    settings: Settings = Conf,
) -> ConnectionOut:
    conn = await service.request_sync(session, ctx, fx, connection_id)
    return await service.to_out(session, ctx, settings, conn)


@router.get("/accounts/{account_id}/ingestion-jobs", response_model=list[IngestionJobOut])
async def ingestion_jobs(
    account_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[IngestionJobOut]:
    """Import history ("ประวัติการนำเข้า")."""
    rows = await service.list_jobs(session, ctx, account_id, limit)
    return [IngestionJobOut.model_validate(j) for j in rows]


def _zip_ea(folder: Path) -> bytes:
    root = folder.resolve()
    if not root.is_dir():
        raise NotFound("EA package not available on this server")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(root)
            if path.is_file() and "tools" not in rel.parts and "__pycache__" not in rel.parts:
                zf.write(path, Path("TrackTrade") / rel)
    return buf.getvalue()


@router.get("/downloads/mt5-ea")
async def download_ea(settings: Settings = Conf) -> Response:
    """The EA folder (`connectors/mt5-ea`: .mq5, include, README, .ex5 when built) as a zip."""
    content = await asyncio.to_thread(_zip_ea, Path(settings.MT5_EA_DIR))
    return Response(
        content=content,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="TrackTrade-MT5-EA.zip"'},
    )


# ------------------------------------------------------------------ EA ingest (API key)


@ingest_router.post("/ingest/events", response_model=IngestOut)
async def ingest_events(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-Api-Key")] = None,
    session: AsyncSession = Db,
    fx: Effects = Fx,
    settings: Settings = Conf,
) -> IngestOut:
    """Deals, positions, SL/TP changes, bars from the EA (connectors/mt5-ea/PROTOCOL.md).
    Idempotent — resending anything is safe (F-08 AC3)."""
    length = request.headers.get("content-length")
    if length is not None and length.isdigit() and int(length) > settings.INGEST_MAX_BYTES:
        raise AppError("payload_too_large", "Split the batch", status_code=413)
    conn = await service.authenticate_key(session, x_api_key)
    redis: Redis = request.app.state.redis
    limit, window = parse_rate(settings.RATE_LIMIT_INGEST)
    allowed, retry_after = await hit(redis, f"ingest:{conn.id}", limit, window)
    if not allowed:
        raise RateLimited(retry_after)
    raw = await request.body()
    if len(raw) > settings.INGEST_MAX_BYTES:
        raise AppError("payload_too_large", "Split the batch", status_code=413)
    try:
        batch = IngestIn.model_validate(json.loads(raw or b"{}"))
    except json.JSONDecodeError as exc:
        raise AppError("invalid_json", "Body is not valid JSON", status_code=422) from exc
    except ValidationError:
        raise
    return await ingest.apply(session, fx, settings, conn, batch)


# ------------------------------------------------------------------ cTrader OAuth


@router.post("/accounts/{account_id}/connections/ctrader/authorize", response_model=AuthorizeOut)
async def ctrader_authorize(
    account_id: uuid.UUID,
    request: Request,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> AuthorizeOut:
    """URL of cTrader's consent page; it comes back to `/connections/ctrader/callback`."""
    account = await accounts_service.get_account(session, ctx, account_id)
    if account.platform != "ctrader":
        raise AppError(
            "platform_mismatch", "cTrader linking is for cTrader accounts", status_code=422
        )
    box = oauth.require_configured(settings)
    state = await oauth.new_state(request.app.state.redis, box, ctx.owner_id, account_id)
    return AuthorizeOut(authorize_url=oauth.authorize_url(settings, state))


public_router = APIRouter(tags=["connections"])


@public_router.get("/connections/ctrader/callback", include_in_schema=True)
async def ctrader_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    session: AsyncSession = Db,
    fx: Effects = Fx,
    settings: Settings = Conf,
) -> RedirectResponse:
    """Browser lands here from cTrader. Authenticated by the sealed one-time `state`, not by a
    session (no bearer token on a redirect). Stores the encrypted tokens and starts the
    90-day history sync (F-08 AC4), then sends the browser back to the Connections tab."""
    back = f"{settings.APP_URL}/accounts"
    if not state:
        return RedirectResponse(f"{back}?tab=connections&ctrader=error&reason=invalid_state", 303)
    box = oauth.require_configured(settings)
    try:
        user_id, account_id = await oauth.read_state(request.app.state.redis, box, state)
    except AppError:
        return RedirectResponse(f"{back}?tab=connections&ctrader=error&reason=invalid_state", 303)
    target = f"{back}?account={account_id}&tab=connections"
    if error or not code:
        return RedirectResponse(f"{target}&ctrader=error&reason={error or 'denied'}", 303)
    try:
        async with httpx.AsyncClient() as http:
            tokens = await oauth.exchange_code(settings, http, code)
    except (CTraderError, httpx.HTTPError):
        return RedirectResponse(f"{target}&ctrader=error&reason=exchange_failed", 303)
    ctx = AccessContext(user_id=user_id)
    conn = await service.save_ctrader_tokens(
        session, ctx, account_id, tokens.sealed(box), tokens.expires_at
    )
    fx.enqueue(session, "sync_ctrader", str(conn.id), True, job_id=f"ctrader:{conn.id}")
    return RedirectResponse(f"{target}&ctrader=connected", 303)
