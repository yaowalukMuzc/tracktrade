from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.modules.auth.deps import get_current
from app.modules.symbols import repo
from app.modules.symbols.schemas import SymbolOut

router = APIRouter(prefix="/symbols", tags=["reference"], dependencies=[Depends(get_current)])


@router.get("", response_model=list[SymbolOut])
async def list_symbols(session: AsyncSession = Depends(get_session)) -> list[SymbolOut]:
    return [SymbolOut.model_validate(s) for s in await repo.list_all(session)]
