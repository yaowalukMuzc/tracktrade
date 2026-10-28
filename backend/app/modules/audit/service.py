"""Audit trail helpers, called by services inside their transaction (PLAN §5.1 `audit`).

Recording happens in the service layer rather than as HTTP middleware because the
entry needs the entity's state before and after the change.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.models_base import Base
from app.modules.audit.models import AuditLog

_SKIP = {"created_at", "updated_at"}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    return value


def snapshot(obj: Base) -> dict[str, Any]:
    """Column values of a model instance as JSON-safe data."""
    mapper = inspect(obj.__class__)
    return {
        col.key: _jsonable(getattr(obj, col.key))
        for col in mapper.column_attrs
        if col.key not in _SKIP
    }


async def record(
    session: AsyncSession,
    ctx: AccessContext,
    *,
    action: str,
    entity: str,
    entity_id: uuid.UUID,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    account_id: uuid.UUID | None = None,
) -> AuditLog | None:
    """Write one entry. An update that changed nothing is not logged."""
    if action == "update" and before == after:
        return None
    if before is not None and after is not None and action == "update":
        changed = {k for k in after if before.get(k) != after.get(k)}
        before = {k: before.get(k) for k in sorted(changed)}
        after = {k: after[k] for k in sorted(changed)}
    entry = AuditLog(
        user_id=ctx.owner_id,
        actor_id=ctx.user_id,
        account_id=account_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_for_account(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, *, limit: int = 100
) -> Sequence[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.user_id == ctx.owner_id, AuditLog.account_id == account_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()
