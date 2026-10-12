from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.symbols.models import Symbol


async def list_all(session: AsyncSession) -> Sequence[Symbol]:
    return (await session.execute(select(Symbol).order_by(Symbol.code))).scalars().all()
