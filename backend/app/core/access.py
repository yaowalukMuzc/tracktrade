"""Ownership policy shared by every module (F-01 AC4).

Rule: every query for user-owned data is filtered by the caller's id *inside the
query*. A row that exists but belongs to someone else is indistinguishable from
a row that does not exist -> 404 `not_found` (never 403, which would leak
existence).

Repos receive an `AccessContext` and use `scoped()` / `get_owned_or_404()`.
Later phases extend the context with the trader being viewed and an active
mentor link (read-only access, `r_only` serialization), without changing call
sites.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.errors import NotFound


@dataclass(frozen=True, slots=True)
class AccessContext:
    """Who is acting. `owner_id` is the user whose data is being accessed."""

    user_id: uuid.UUID

    @property
    def owner_id(self) -> uuid.UUID:
        # Phase 8 (mentorship) will allow owner_id != user_id via an active link.
        return self.user_id


def scoped[*Ts](
    stmt: Select[*Ts], owner_column: InstrumentedAttribute[uuid.UUID], ctx: AccessContext
) -> Select[*Ts]:
    """Add the owner filter to a SELECT."""
    return stmt.where(owner_column == ctx.owner_id)


async def get_owned_or_404[T](
    session: AsyncSession,
    model: type[T],
    obj_id: uuid.UUID,
    ctx: AccessContext,
    *,
    owner_attr: str = "user_id",
) -> T:
    """Load `model` by id only if it belongs to the context owner, else 404."""
    id_col: InstrumentedAttribute[uuid.UUID] = getattr(model, "id")  # noqa: B009
    owner_col: InstrumentedAttribute[uuid.UUID] = getattr(model, owner_attr)
    stmt = scoped(select(model).where(id_col == obj_id), owner_col, ctx)
    obj = (await session.execute(stmt)).scalar_one_or_none()
    if obj is None:
        raise NotFound()
    return obj
