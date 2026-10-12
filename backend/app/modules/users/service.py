from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User
from app.modules.users.schemas import UserUpdate


async def update_profile(session: AsyncSession, user: User, patch: UserUpdate) -> User:
    for field, value in patch.model_dump(exclude_unset=True).items():
        if value is not None:  # explicit nulls are ignored: all fields are non-nullable
            setattr(user, field, value)
    await session.flush()
    await session.refresh(user)
    return user
