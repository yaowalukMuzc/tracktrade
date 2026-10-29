"""`/positions` — trades list, manual entry, detail, matching (F-07, F-10)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.config import Settings
from app.core.db import get_session
from app.core.effects import Effects, get_effects
from app.modules.auth.deps import get_access_context
from app.modules.positions import service
from app.modules.positions.schemas import (
    Direction,
    ListFilters,
    ManualPositionIn,
    MatchCandidate,
    MatchIn,
    MatchQueueItem,
    PositionCalcOut,
    PositionList,
    PositionOut,
    Tab,
)

router = APIRouter(prefix="/positions", tags=["positions"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)
Fx = Depends(get_effects)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


Conf = Depends(get_settings_dep)


def filters(
    tab: Tab = "all",
    account_id: uuid.UUID | None = None,
    symbol_id: uuid.UUID | None = None,
    setup_id: uuid.UUID | None = None,
    direction: Direction | None = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    q: Annotated[str, Query(max_length=60)] = "",
) -> ListFilters:
    return ListFilters(
        tab=tab,
        account_id=account_id,
        symbol_id=symbol_id,
        setup_id=setup_id,
        direction=direction,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )


@router.get("", response_model=PositionList)
async def list_positions(
    f: ListFilters = Depends(filters),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> PositionList:
    """Tabs all / review / pending / unplanned / open with per-tab counts (screens 06, 09)."""
    return await service.list_positions(session, ctx, f, offset=offset, limit=limit)


@router.post("", response_model=PositionOut, status_code=status.HTTP_201_CREATED)
async def create_position(
    body: ManualPositionIn,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    fx: Effects = Fx,
    settings: Settings = Conf,
) -> PositionOut:
    """Manual trade with executions (F-07 AC1-AC3)."""
    return await service.create_manual(session, ctx, fx, settings, body)


@router.post("/preview", response_model=PositionCalcOut)
async def preview_position(
    body: ManualPositionIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PositionCalcOut:
    """Averages / P&L / R / unplanned warning for the form, without saving (F-07 AC2)."""
    return await service.preview(session, ctx, body)


@router.get("/plan-options", response_model=list[MatchCandidate])
async def plan_options(
    account_id: uuid.UUID,
    symbol_id: uuid.UUID,
    direction: Direction,
    opened_at: datetime,
    entry_price: Annotated[Decimal, Query(gt=0)],
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> list[MatchCandidate]:
    """Plans the manual form can link to, drafts included (they make the trade unplanned)."""
    return await service.plan_options(
        session,
        ctx,
        settings,
        account_id=account_id,
        symbol_id=symbol_id,
        direction=direction,
        opened_at=opened_at,
        entry_price=entry_price,
    )


@router.get("/match-queue", response_model=list[MatchQueueItem])
async def match_queue(
    account_id: uuid.UUID | None = None,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> list[MatchQueueItem]:
    """Trades waiting for the trader to pick a plan (F-10 AC2), oldest first."""
    return await service.match_queue(session, ctx, settings, account_id)


@router.get("/export.csv")
async def export_csv(
    f: ListFilters = Depends(filters), ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    body = await service.export_csv(session, ctx, f)
    return Response(
        content="﻿" + body,  # BOM so Excel opens Thai text as UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="tracktrade-trades.csv"'},
    )


@router.get("/{position_id}", response_model=PositionOut)
async def get_position(
    position_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PositionOut:
    return await service.detail(session, ctx, position_id)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db, fx: Effects = Fx
) -> Response:
    await service.delete_position(session, ctx, fx, position_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{position_id}/match-candidates", response_model=list[MatchCandidate])
async def match_candidates(
    position_id: uuid.UUID,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    settings: Settings = Conf,
) -> list[MatchCandidate]:
    return await service.match_candidates(session, ctx, settings, position_id)


@router.put("/{position_id}/match", response_model=PositionOut)
async def set_match(
    position_id: uuid.UUID,
    body: MatchIn,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
    fx: Effects = Fx,
) -> PositionOut:
    """Pick the plan, or `null` for unplanned (F-10 AC3)."""
    return await service.set_match(session, ctx, fx, position_id, body.plan_id)
