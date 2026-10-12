from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.modules.emotions.models import EmotionTag


async def list_visible(session: AsyncSession, ctx: AccessContext) -> Sequence[EmotionTag]:
    """System tags (user_id NULL) + the caller's own custom tags."""
    stmt = (
        select(EmotionTag)
        .where(or_(EmotionTag.user_id.is_(None), EmotionTag.user_id == ctx.owner_id))
        .order_by(EmotionTag.user_id.is_not(None), EmotionTag.valence, EmotionTag.code)
    )
    return (await session.execute(stmt)).scalars().all()
