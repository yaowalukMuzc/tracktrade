"""`/plans` — trade plans, lock, revisions, status (F-06)."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.auth.deps import get_access_context
from app.modules.plans import service
from app.modules.plans.schemas import (
    EmotionIn,
    PlanBrief,
    PlanCreate,
    PlanOut,
    PlanStatus,
    PlanUpdate,
    RevisionIn,
    RevisionOut,
    RevisionPreviewIn,
    StatusIn,
)

router = APIRouter(prefix="/plans", tags=["plans"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)


@router.get("", response_model=list[PlanBrief])
async def list_plans(
    plan_date: date | None = Query(None, alias="date"),
    status_: PlanStatus | None = Query(None, alias="status"),
    analysis_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> list[PlanBrief]:
    return await service.briefs(
        session,
        ctx,
        plan_date=plan_date,
        status=status_,
        analysis_id=analysis_id,
        account_id=account_id,
    )


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: PlanCreate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.create(session, ctx, body)


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.detail(session, ctx, plan_id)


@router.patch("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID, body: PlanUpdate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.update(session, ctx, plan_id, body)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    await service.delete_plan(session, ctx, plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{plan_id}/pre-emotion", response_model=PlanOut)
async def put_pre_emotion(
    plan_id: uuid.UUID, body: EmotionIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.set_pre_emotion(session, ctx, plan_id, body)


@router.post("/{plan_id}/lock", response_model=PlanOut)
async def lock_plan(
    plan_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.lock(session, ctx, plan_id)


@router.get("/{plan_id}/revisions", response_model=list[RevisionOut])
async def list_revisions(
    plan_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> list[RevisionOut]:
    return await service.list_revisions(session, ctx, plan_id)


@router.post(
    "/{plan_id}/revisions", response_model=RevisionOut, status_code=status.HTTP_201_CREATED
)
async def create_revision(
    plan_id: uuid.UUID, body: RevisionIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> RevisionOut:
    return await service.revise(session, ctx, plan_id, body.changes, body.reason)


@router.post("/{plan_id}/revisions/preview", response_model=RevisionOut)
async def preview_revision(
    plan_id: uuid.UUID,
    body: RevisionPreviewIn,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> RevisionOut:
    """What the revision would change, incl. the risk delta and the after-entry flag; not saved."""
    return await service.revise(session, ctx, plan_id, body.changes, None, dry_run=True)


@router.post("/{plan_id}/status", response_model=PlanOut)
async def change_status(
    plan_id: uuid.UUID, body: StatusIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> PlanOut:
    return await service.set_status(session, ctx, plan_id, body)
