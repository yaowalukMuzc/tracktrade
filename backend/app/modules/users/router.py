"""`/me` profile and preferences. Signed-in devices are managed by Better Auth."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.deps import CurrentUser, get_current
from app.modules.users import service
from app.modules.users.schemas import UserOut, UserUpdate

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
