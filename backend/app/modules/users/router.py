"""`/me` profile + signed-in devices (sessions)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth import service as auth_service
from app.modules.auth.deps import CurrentUser, get_current
from app.modules.users import service
from app.modules.users.schemas import SessionOut, UserOut, UserUpdate

router = APIRouter(prefix="/me", tags=["users"])


@router.get("", response_model=UserOut)
async def get_me(current: CurrentUser = Depends(get_current)) -> UserOut:
    return UserOut.model_validate(current.user)


@router.patch("", response_model=UserOut)
async def patch_me(
    body: UserUpdate,
    current: CurrentUser = Depends(get_current),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await service.update_profile(session, current.user, body)
    return UserOut.model_validate(user)


@router.get("/sessions", response_model=list[SessionOut])
async def list_sessions(
    current: CurrentUser = Depends(get_current),
    session: AsyncSession = Depends(get_session),
) -> list[SessionOut]:
    return await auth_service.list_sessions(
        session, current.ctx, current_session_id=current.claims.session_id
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_session(
    session_id: uuid.UUID,
    current: CurrentUser = Depends(get_current),
    session: AsyncSession = Depends(get_session),
) -> Response:
    await auth_service.revoke_session(session, current.ctx, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
