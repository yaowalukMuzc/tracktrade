from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.auth.deps import get_access_context
from app.modules.emotions import repo
from app.modules.emotions.schemas import EmotionTagOut

router = APIRouter(prefix="/emotion-tags", tags=["reference"])


@router.get("", response_model=list[EmotionTagOut])
async def list_emotion_tags(
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> list[EmotionTagOut]:
    return [
        EmotionTagOut(
            id=t.id,
            code=t.code,
            label_th=t.label_th,
            label_en=t.label_en,
            valence=t.valence,
            is_system=t.user_id is None,
        )
        for t in await repo.list_visible(session, ctx)
    ]
