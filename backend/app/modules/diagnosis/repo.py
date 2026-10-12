from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.diagnosis.models import DIMENSIONS, MistakeCategory

_DIMENSION_ORDER = case({d: i for i, d in enumerate(DIMENSIONS)}, value=MistakeCategory.dimension)


async def list_all(session: AsyncSession) -> Sequence[MistakeCategory]:
    stmt = select(MistakeCategory).order_by(_DIMENSION_ORDER, MistakeCategory.code)
    return (await session.execute(stmt)).scalars().all()
