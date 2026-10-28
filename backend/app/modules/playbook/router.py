"""`/setups` — Playbook (F-04)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.core.storage import Storage
from app.modules.auth.deps import get_access_context
from app.modules.playbook import service
from app.modules.playbook.schemas import (
    ChecklistItemIn,
    ExampleIn,
    SetupCreate,
    SetupListOut,
    SetupOut,
    SetupStats,
    SetupUpdate,
)

router = APIRouter(prefix="/setups", tags=["playbook"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)


@router.get("", response_model=SetupListOut)
async def list_setups(
    archived: bool = Query(False), ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupListOut:
    return await service.list_setups(session, ctx, archived=archived)


@router.post("", response_model=SetupOut, status_code=status.HTTP_201_CREATED)
async def create_setup(
    body: SetupCreate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.create(session, ctx, body)


@router.get("/{setup_id}", response_model=SetupOut)
async def get_setup(
    setup_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.detail(session, ctx, setup_id)


@router.patch("/{setup_id}", response_model=SetupOut)
async def update_setup(
    setup_id: uuid.UUID, body: SetupUpdate, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.update(session, ctx, setup_id, body)


@router.delete("/{setup_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setup(
    setup_id: uuid.UUID, request: Request, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> Response:
    keys = await service.delete(session, ctx, setup_id)
    await session.commit()  # files go only after the rows are gone for good
    storage: Storage = request.app.state.storage
    for key in keys:
        await storage.delete(key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{setup_id}/checklist", response_model=SetupOut)
async def put_checklist(
    setup_id: uuid.UUID,
    items: list[ChecklistItemIn],
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> SetupOut:
    return await service.replace_checklist(session, ctx, setup_id, items[:30])


@router.post("/{setup_id}/archive", response_model=SetupOut)
async def archive_setup(
    setup_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.set_archived(session, ctx, setup_id, True)


@router.post("/{setup_id}/unarchive", response_model=SetupOut)
async def unarchive_setup(
    setup_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.set_archived(session, ctx, setup_id, False)


@router.post("/{setup_id}/examples", response_model=SetupOut, status_code=status.HTTP_201_CREATED)
async def add_example(
    setup_id: uuid.UUID, body: ExampleIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupOut:
    return await service.add_example(session, ctx, setup_id, body)


@router.delete("/{setup_id}/examples/{example_id}", response_model=SetupOut)
async def remove_example(
    setup_id: uuid.UUID,
    example_id: uuid.UUID,
    request: Request,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> SetupOut:
    result, key = await service.remove_example(session, ctx, setup_id, example_id)
    await session.commit()
    if key:
        storage: Storage = request.app.state.storage
        await storage.delete(key)
    return result


@router.get("/{setup_id}/stats", response_model=SetupStats)
async def setup_stats(
    setup_id: uuid.UUID, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> SetupStats:
    """F-04 AC3 — computed from trades in Phase 7; empty until then."""
    await service.detail(session, ctx, setup_id)
    return SetupStats()
