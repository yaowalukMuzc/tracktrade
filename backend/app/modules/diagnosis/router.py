from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.deps import get_current
from app.modules.diagnosis import repo
from app.modules.diagnosis.schemas import MistakeCategoryOut

router = APIRouter(
    prefix="/mistake-categories", tags=["reference"], dependencies=[Depends(get_current)]
)


@router.get("", response_model=list[MistakeCategoryOut])
async def list_mistake_categories(
    session: AsyncSession = Depends(get_session),
) -> list[MistakeCategoryOut]:
    return [MistakeCategoryOut.model_validate(c) for c in await repo.list_all(session)]
