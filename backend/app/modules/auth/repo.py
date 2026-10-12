from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, scoped
from app.modules.auth.models import RefreshToken


async def get_by_hash_for_update(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def revoke_family(
    session: AsyncSession, family_id: uuid.UUID, now: datetime, *, user_id: uuid.UUID | None = None
) -> int:
    """Revoke every still-valid token in a family. Returns rows affected."""
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if user_id is not None:
        stmt = stmt.where(RefreshToken.user_id == user_id)
    result = await session.execute(stmt)
    return int(result.rowcount)  # type: ignore[attr-defined]


async def family_head_for_update(
    session: AsyncSession, family_id: uuid.UUID
) -> RefreshToken | None:
    """The family's current token (not rotated, not revoked), row-locked."""
    stmt = (
        select(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.rotated_at.is_(None),
            RefreshToken.revoked_at.is_(None),
        )
        .order_by(RefreshToken.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def active_heads(
    session: AsyncSession, ctx: AccessContext, now: datetime
) -> list[tuple[RefreshToken, datetime]]:
    """Current (un-rotated, un-revoked, unexpired) token of each family + family start."""
    started = (
        select(RefreshToken.family_id, func.min(RefreshToken.created_at).label("started_at"))
        .group_by(RefreshToken.family_id)
        .subquery()
    )
    stmt = scoped(
        select(RefreshToken, started.c.started_at)
        .join(started, started.c.family_id == RefreshToken.family_id)
        .where(
            RefreshToken.revoked_at.is_(None),
            RefreshToken.rotated_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .order_by(RefreshToken.last_used_at.desc().nulls_last(), RefreshToken.created_at.desc()),
        RefreshToken.user_id,
        ctx,
    )
    return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]


async def owned_family_exists(
    session: AsyncSession, ctx: AccessContext, family_id: uuid.UUID, now: datetime
) -> bool:
    stmt = scoped(
        select(RefreshToken.id).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        ),
        RefreshToken.user_id,
        ctx,
    ).limit(1)
    return (await session.execute(stmt)).first() is not None
