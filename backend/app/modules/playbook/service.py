"""Playbook rules (F-04): setups, ordered checklist, examples, archive-not-delete when used."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import AppError, Conflict, NotFound
from app.modules.attachments.models import Attachment
from app.modules.audit.service import record, snapshot
from app.modules.playbook.models import Setup, SetupChecklistItem, SetupExample
from app.modules.playbook.schemas import (
    ChecklistItemIn,
    ChecklistItemOut,
    ExampleIn,
    ExampleOut,
    ManagementRules,
    SetupCounts,
    SetupCreate,
    SetupListOut,
    SetupOut,
    SetupStats,
    SetupSummary,
    SetupUpdate,
)

MAX_EXAMPLES = 12


async def _get(session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID) -> Setup:
    return await get_owned_or_404(session, Setup, setup_id, ctx)


async def _checklist(session: AsyncSession, setup_id: uuid.UUID) -> Sequence[SetupChecklistItem]:
    stmt = (
        select(SetupChecklistItem)
        .where(SetupChecklistItem.setup_id == setup_id)
        .order_by(SetupChecklistItem.position)
    )
    return (await session.execute(stmt)).scalars().all()


async def _examples(session: AsyncSession, setup_id: uuid.UUID) -> Sequence[SetupExample]:
    stmt = (
        select(SetupExample)
        .where(SetupExample.setup_id == setup_id)
        .order_by(SetupExample.position, SetupExample.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


def _summary(setup: Setup, checklist_count: int) -> SetupSummary:
    return SetupSummary(
        id=setup.id,
        name=setup.name,
        timeframes=setup.timeframes,
        sessions=setup.sessions,
        default_risk_pct=setup.default_risk_pct,
        is_archived=setup.is_archived,
        checklist_count=checklist_count,
        stats=SetupStats(),
    )


async def detail(session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID) -> SetupOut:
    setup = await _get(session, ctx, setup_id)
    items = await _checklist(session, setup.id)
    examples = await _examples(session, setup.id)
    return SetupOut(
        **_summary(setup, len(items)).model_dump(),
        description=setup.description,
        management_rules=ManagementRules.model_validate(setup.management_rules or {}),
        checklist=[ChecklistItemOut.model_validate(i) for i in items],
        examples=[
            ExampleOut(
                id=e.id,
                attachment_id=e.attachment_id,
                url=f"/api/v1/attachments/{e.attachment_id}/content",
                note=e.note,
            )
            for e in examples
        ],
        created_at=setup.created_at,
        updated_at=setup.updated_at,
    )


async def list_setups(session: AsyncSession, ctx: AccessContext, *, archived: bool) -> SetupListOut:
    counts_stmt = (
        select(Setup.is_archived, func.count())
        .where(Setup.user_id == ctx.owner_id)
        .group_by(Setup.is_archived)
    )
    counts = {bool(a): int(n) for a, n in (await session.execute(counts_stmt)).all()}
    n_items = (
        select(func.count())
        .where(SetupChecklistItem.setup_id == Setup.id)
        .correlate(Setup)
        .scalar_subquery()
    )
    stmt = (
        select(Setup, n_items)
        .where(Setup.user_id == ctx.owner_id, Setup.is_archived.is_(archived))
        .order_by(Setup.created_at)
    )
    rows = (await session.execute(stmt)).all()
    return SetupListOut(
        items=[_summary(s, int(n)) for s, n in rows],
        counts=SetupCounts(active=counts.get(False, 0), archived=counts.get(True, 0)),
    )


async def _replace_checklist(
    session: AsyncSession, setup: Setup, items: list[ChecklistItemIn]
) -> None:
    existing = {i.id: i for i in await _checklist(session, setup.id)}
    keep: set[uuid.UUID] = set()
    for position, item in enumerate(items):
        if item.id is not None:
            row = existing.get(item.id)
            if row is None:
                raise AppError(
                    "unknown_checklist_item",
                    "Checklist item does not belong to this setup",
                    status_code=422,
                    details={"id": str(item.id)},
                )
            row.text, row.is_required, row.position = item.text, item.is_required, position
            keep.add(row.id)
        else:
            session.add(
                SetupChecklistItem(
                    setup_id=setup.id,
                    position=position,
                    text=item.text,
                    is_required=item.is_required,
                )
            )
    for item_id, row in existing.items():
        if item_id not in keep:
            await session.delete(row)
    await session.flush()


async def create(session: AsyncSession, ctx: AccessContext, body: SetupCreate) -> SetupOut:
    setup = Setup(
        user_id=ctx.owner_id,
        name=body.name,
        description=body.description,
        timeframes=list(body.timeframes),
        sessions=list(body.sessions),
        default_risk_pct=body.default_risk_pct,
        management_rules=body.management_rules.model_dump(mode="json"),
    )
    session.add(setup)
    await session.flush()
    for item in body.checklist:
        item.id = None  # a new setup has no existing items
    await _replace_checklist(session, setup, body.checklist)
    await session.refresh(setup)
    await record(
        session, ctx, action="create", entity="setup", entity_id=setup.id, after=snapshot(setup)
    )
    return await detail(session, ctx, setup.id)


async def update(
    session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID, patch: SetupUpdate
) -> SetupOut:
    setup = await _get(session, ctx, setup_id)
    before = snapshot(setup)
    data = patch.model_dump(exclude_unset=True, exclude_none=True, mode="json")
    for key, value in data.items():
        setattr(setup, key, value)
    await session.flush()
    await session.refresh(setup)
    await record(
        session,
        ctx,
        action="update",
        entity="setup",
        entity_id=setup.id,
        before=before,
        after=snapshot(setup),
    )
    return await detail(session, ctx, setup.id)


async def replace_checklist(
    session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID, items: list[ChecklistItemIn]
) -> SetupOut:
    setup = await _get(session, ctx, setup_id)
    before = [
        ChecklistItemOut.model_validate(i).model_dump(mode="json")
        for i in await _checklist(session, setup.id)
    ]
    await _replace_checklist(session, setup, items)
    after = [
        ChecklistItemOut.model_validate(i).model_dump(mode="json")
        for i in await _checklist(session, setup.id)
    ]
    await record(
        session,
        ctx,
        action="update",
        entity="setup_checklist",
        entity_id=setup.id,
        before={"items": before},
        after={"items": after},
    )
    return await detail(session, ctx, setup.id)


async def set_archived(
    session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID, archived: bool
) -> SetupOut:
    setup = await _get(session, ctx, setup_id)
    if setup.is_archived != archived:
        setup.is_archived = archived
        await session.flush()
        await record(
            session,
            ctx,
            action="archive" if archived else "unarchive",
            entity="setup",
            entity_id=setup.id,
            after={"is_archived": archived},
        )
    return await detail(session, ctx, setup.id)


async def delete(session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID) -> list[str]:
    """F-04 AC2: anything that references the setup (trade plans, Phase 3) blocks the delete.

    Returns the storage keys of the example images, to remove once the transaction commits."""
    setup = await _get(session, ctx, setup_id)
    before = snapshot(setup)
    examples = await _examples(session, setup.id)
    attachment_ids = [e.attachment_id for e in examples]
    try:
        async with session.begin_nested():
            await session.delete(setup)
            await session.flush()
    except IntegrityError as exc:
        raise Conflict(
            "setup_in_use", "This setup is used by trade plans; archive it instead"
        ) from exc
    # Example images belong to the setup only.
    keys = []
    for att_id in attachment_ids:
        att = await session.get(Attachment, att_id)
        if att is not None:
            keys.append(att.storage_key)
            await session.delete(att)
    await session.flush()
    await record(session, ctx, action="delete", entity="setup", entity_id=setup_id, before=before)
    return keys


async def add_example(
    session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID, body: ExampleIn
) -> SetupOut:
    setup = await _get(session, ctx, setup_id)
    await get_owned_or_404(session, Attachment, body.attachment_id, ctx)
    examples = await _examples(session, setup.id)
    if len(examples) >= MAX_EXAMPLES:
        raise AppError(
            "too_many_examples", f"At most {MAX_EXAMPLES} example images", status_code=422
        )
    session.add(
        SetupExample(
            setup_id=setup.id,
            attachment_id=body.attachment_id,
            note=body.note,
            position=len(examples),
        )
    )
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError as exc:
        raise Conflict("attachment_in_use", "This image is already used") from exc
    return await detail(session, ctx, setup.id)


async def remove_example(
    session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID, example_id: uuid.UUID
) -> tuple[SetupOut, str | None]:
    """Removes the example and its image; returns the storage key to delete after commit."""
    setup = await _get(session, ctx, setup_id)
    stmt = select(SetupExample).where(
        SetupExample.id == example_id, SetupExample.setup_id == setup.id
    )
    example = (await session.execute(stmt)).scalar_one_or_none()
    if example is None:
        raise NotFound()
    att = await session.get(Attachment, example.attachment_id)
    key = att.storage_key if att else None
    await session.delete(example)
    await session.flush()
    if att is not None:
        await session.delete(att)
        await session.flush()
    return await detail(session, ctx, setup.id), key
