"""`/analyses` (F-05), `/chart-drawings` (F-19 AC3), `/market-data/ohlc` (mock until Phase 4)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.analysis import service
from app.modules.analysis.schemas import (
    AnalysisCreate,
    AnalysisOut,
    AnalysisSummary,
    AnalysisUpdate,
    DrawingOut,
    DrawingOwner,
    DrawingsPut,
    OhlcOut,
)
from app.modules.auth.deps import get_access_context
from app.modules.playbook.schemas import Timeframe

router = APIRouter(tags=["analysis"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)


@router.get("/analyses", response_model=list[AnalysisSummary])
async def list_analyses(
    on: date | None = Query(None, alias="date"),
    symbol_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[AnalysisSummary]:
    return await service.list_analyses(
        session, ctx, on=on, symbol_id=symbol_id, account_id=account_id, limit=limit
    )


@router.post("/analyses", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    body: AnalysisCreate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AnalysisOut:
    return await service.create(session, ctx, body)


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
async def get_analysis(
    analysis_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> AnalysisOut:
    return await service.detail(session, ctx, analysis_id)


@router.patch("/analyses/{analysis_id}", response_model=AnalysisOut)
async def update_analysis(
    analysis_id: uuid.UUID,
    body: AnalysisUpdate,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> AnalysisOut:
    return await service.update(session, ctx, analysis_id, body)


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_analysis(
    analysis_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    await service.delete_analysis(session, ctx, analysis_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/chart-drawings", response_model=list[DrawingOut])
async def get_drawings(
    owner_type: DrawingOwner,
    owner_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[DrawingOut]:
    return await service.list_drawings(session, ctx, owner_type, owner_id)


@router.put("/chart-drawings", response_model=list[DrawingOut])
async def put_drawings(
    owner_type: DrawingOwner,
    owner_id: uuid.UUID,
    body: DrawingsPut,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[DrawingOut]:
    return await service.put_drawings(session, ctx, owner_type, owner_id, body)


@router.get("/market-data/ohlc", response_model=OhlcOut)
async def get_ohlc(
    symbol_id: uuid.UUID,
    tf: Timeframe = "H1",
    to: Annotated[int | None, Query(ge=0, description="unix seconds, default now")] = None,
    count: Annotated[int, Query(ge=10, le=1000)] = 300,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> OhlcOut:
    """Bars for the chart. Synthetic ("source": "mock") until broker OHLC arrives in Phase 4."""
    return await service.ohlc(session, ctx, symbol_id=symbol_id, timeframe=tf, to=to, count=count)
