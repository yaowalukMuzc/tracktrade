"""Trade plans (F-06): draft → lock (hash) → append-only revisions → status changes / expiry."""

from __future__ import annotations

import string
import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import AppError, Conflict, NotFound
from app.modules.accounts import service as accounts
from app.modules.accounts.models import TradingAccount
from app.modules.analysis.models import ChartDrawing, MarketAnalysis
from app.modules.audit.service import record
from app.modules.emotions.models import EmotionLog, EmotionTag
from app.modules.plans import snapshot as snap
from app.modules.plans.models import PlanChecklistAnswer, TradePlan, TradePlanRevision
from app.modules.plans.schemas import (
    CalcMeta,
    ChecklistAnswerIn,
    ChecklistItemState,
    ChecklistStatus,
    EmotionIn,
    EmotionOut,
    ManagementPlan,
    PlanBrief,
    PlanCreate,
    PlanOut,
    PlanUpdate,
    RevisionChanges,
    RevisionOut,
    StatusIn,
    TakeProfitOut,
)
from app.modules.playbook.models import Setup, SetupChecklistItem
from app.modules.risk.calculator import TakeProfit
from app.modules.risk.service import RiskCalcOut, compute
from app.modules.symbols.models import Symbol
from app.modules.users.models import User

CENT = Decimal("0.01")
# skipped / invalidated before or after the lock; "missed" only makes sense for a locked plan.
MANUAL_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "skipped": ("draft", "locked"),
    "invalidated": ("draft", "locked"),
    "missed": ("locked",),
}
OPEN_STATUSES = ("draft", "locked")


def utcnow() -> datetime:
    return datetime.now(UTC)


async def user_zone(session: AsyncSession, ctx: AccessContext) -> ZoneInfo:
    user = await session.get(User, ctx.owner_id)
    try:
        return ZoneInfo(user.timezone if user else "UTC")
    except (KeyError, ValueError):
        return ZoneInfo("UTC")


def local_today(tz: ZoneInfo) -> date:
    return datetime.now(tz).date()


def end_of_day(day: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, time(23, 59, 59), tzinfo=tz)


# ------------------------------------------------------------------ helpers


async def _get(session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID) -> TradePlan:
    return await get_owned_or_404(session, TradePlan, plan_id, ctx)


async def _items(session: AsyncSession, setup_id: uuid.UUID) -> Sequence[SetupChecklistItem]:
    stmt = (
        select(SetupChecklistItem)
        .where(SetupChecklistItem.setup_id == setup_id)
        .order_by(SetupChecklistItem.position)
    )
    return (await session.execute(stmt)).scalars().all()


async def _answers(
    session: AsyncSession, plan_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[uuid.UUID, PlanChecklistAnswer]]:
    out: dict[uuid.UUID, dict[uuid.UUID, PlanChecklistAnswer]] = defaultdict(dict)
    if plan_ids:
        stmt = select(PlanChecklistAnswer).where(PlanChecklistAnswer.plan_id.in_(plan_ids))
        for a in (await session.execute(stmt)).scalars():
            out[a.plan_id][a.checklist_item_id] = a
    return out


def _status(
    items: Sequence[SetupChecklistItem], answers: dict[uuid.UUID, PlanChecklistAnswer]
) -> ChecklistStatus:
    def on(item: SetupChecklistItem) -> bool:
        a = answers.get(item.id)
        return bool(a and a.checked)

    required = [i for i in items if i.is_required]
    return ChecklistStatus(
        done=sum(on(i) for i in items),
        total=len(items),
        required_done=sum(on(i) for i in required),
        required_total=len(required),
        missing=[i.id for i in required if not on(i)],
    )


def _frozen_status(checklist: list[dict[str, Any]]) -> ChecklistStatus:
    """Checklist as locked (revision snapshot) — later setup edits don't change a locked plan."""
    required = [c for c in checklist if c["is_required"]]
    return ChecklistStatus(
        done=sum(bool(c["checked"]) for c in checklist),
        total=len(checklist),
        required_done=sum(bool(c["checked"]) for c in required),
        required_total=len(required),
        missing=[uuid.UUID(c["item_id"]) for c in required if not c["checked"]],
    )


def _tps(plan: TradePlan, rrs: Sequence[Decimal | None] | None = None) -> list[TakeProfitOut]:
    out = []
    risk = abs(plan.entry_price - plan.stop_loss)
    for i, tp in enumerate(plan.take_profits):
        price = Decimal(str(tp["price"]))
        rr = rrs[i] if rrs and i < len(rrs) else None
        if rr is None and risk > 0:
            rr = (abs(price - plan.entry_price) / risk).quantize(CENT)
        out.append(TakeProfitOut(price=price, pct=Decimal(str(tp.get("pct", 100))), rr=rr))
    return out


def _tp_inputs(tps: list[dict[str, Any]]) -> list[TakeProfit]:
    return [TakeProfit(Decimal(str(tp["price"])), Decimal(str(tp.get("pct", 100)))) for tp in tps]


def _tps_json(tps: Sequence[Any]) -> list[dict[str, str]]:
    """Pydantic TakeProfitIn models or dicts → stored JSON."""
    out = []
    for tp in tps:
        price = tp.price if hasattr(tp, "price") else tp["price"]
        pct = tp.pct if hasattr(tp, "pct") else tp.get("pct", 100)
        out.append({"price": snap.dec(price) or "0", "pct": snap.dec(pct) or "100"})
    return out


async def _calc(
    session: AsyncSession,
    ctx: AccessContext,
    account: TradingAccount,
    *,
    symbol_id: uuid.UUID,
    direction: str,
    entry: Decimal,
    stop_loss: Decimal,
    take_profits: list[dict[str, Any]],
    rate: Decimal | None,
    risk_pct: Decimal | None = None,
    lot: Decimal | None = None,
) -> RiskCalcOut:
    return await compute(
        session,
        ctx,
        account,
        symbol_id=symbol_id,
        direction="long" if direction == "long" else "short",
        entry=entry,
        stop_loss=stop_loss,
        take_profits=_tp_inputs(take_profits),
        risk_pct=risk_pct,
        lot=lot,
        quote_to_account_rate=rate,
    )


async def _account(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> TradingAccount:
    account = await accounts.get_account(session, ctx, account_id)
    if not account.is_active:
        raise AppError("account_archived", "This account is archived", status_code=422)
    return account


async def _setup(session: AsyncSession, ctx: AccessContext, setup_id: uuid.UUID) -> Setup:
    setup = await get_owned_or_404(session, Setup, setup_id, ctx)
    if setup.is_archived:
        raise AppError("setup_archived", "This setup is archived", status_code=422)
    return setup


async def _replace_answers(
    session: AsyncSession, plan: TradePlan, answers: list[ChecklistAnswerIn]
) -> None:
    valid = {i.id for i in await _items(session, plan.setup_id)}
    for a in answers:
        if a.checklist_item_id not in valid:
            raise AppError(
                "unknown_checklist_item",
                "Checklist item does not belong to the plan's setup",
                status_code=422,
                details={"id": str(a.checklist_item_id)},
            )
    await session.execute(delete(PlanChecklistAnswer).where(PlanChecklistAnswer.plan_id == plan.id))
    seen: set[uuid.UUID] = set()
    for a in answers:
        if a.checklist_item_id in seen:
            continue
        seen.add(a.checklist_item_id)
        session.add(
            PlanChecklistAnswer(
                plan_id=plan.id,
                checklist_item_id=a.checklist_item_id,
                checked=a.checked,
                note=a.note,
            )
        )
    await session.flush()


async def validate_tags(session: AsyncSession, ctx: AccessContext, tags: list[uuid.UUID]) -> None:
    if not tags:
        return
    stmt = select(EmotionTag.id).where(
        EmotionTag.id.in_(tags),
        or_(EmotionTag.user_id.is_(None), EmotionTag.user_id == ctx.owner_id),
    )
    found = set((await session.execute(stmt)).scalars())
    unknown = [str(t) for t in tags if t not in found]
    if unknown:
        raise AppError(
            "unknown_emotion_tag", "Unknown emotion tag", status_code=422, details={"ids": unknown}
        )


async def _pre_emotion(session: AsyncSession, plan_id: uuid.UUID) -> EmotionLog | None:
    stmt = select(EmotionLog).where(
        EmotionLog.owner_type == "plan", EmotionLog.owner_id == plan_id, EmotionLog.phase == "pre"
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _set_pre_emotion(
    session: AsyncSession, ctx: AccessContext, plan: TradePlan, body: EmotionIn
) -> None:
    """F-06 AC7 / F-11 AC1: one pre-trade log per plan, replaced on edit."""
    tags = list(dict.fromkeys(body.tags))
    await validate_tags(session, ctx, tags)
    log = await _pre_emotion(session, plan.id)
    if log is None:
        log = EmotionLog(user_id=ctx.owner_id, owner_type="plan", owner_id=plan.id, phase="pre")
        session.add(log)
    log.mood, log.confidence, log.tags, log.note = body.mood, body.confidence, tags, body.note
    log.logged_at = utcnow()
    await session.flush()


async def _next_scenario(session: AsyncSession, analysis_id: uuid.UUID | None) -> str:
    if analysis_id is None:
        return "A"
    stmt = select(TradePlan.scenario_label).where(TradePlan.analysis_id == analysis_id)
    used = set((await session.execute(stmt)).scalars())
    return next((c for c in string.ascii_uppercase if c not in used), "Z")


async def _revisions(session: AsyncSession, plan_id: uuid.UUID) -> Sequence[TradePlanRevision]:
    stmt = (
        select(TradePlanRevision)
        .where(TradePlanRevision.plan_id == plan_id)
        .order_by(TradePlanRevision.revision_no)
    )
    return (await session.execute(stmt)).scalars().all()


async def _live_checklist(session: AsyncSession, plan: TradePlan) -> list[dict[str, Any]]:
    items = await _items(session, plan.setup_id)
    answers = (await _answers(session, [plan.id])).get(plan.id, {})
    return [
        {
            "item_id": i.id,
            "text": i.text,
            "is_required": i.is_required,
            "checked": bool(answers.get(i.id) and answers[i.id].checked),
            "note": answers[i.id].note if i.id in answers else "",
        }
        for i in items
    ]


# ------------------------------------------------------------------ read


async def briefs(
    session: AsyncSession,
    ctx: AccessContext,
    *,
    plan_date: date | None = None,
    status: str | None = None,
    analysis_id: uuid.UUID | None = None,
    account_id: uuid.UUID | None = None,
) -> list[PlanBrief]:
    stmt = (
        select(TradePlan, Setup.name, Symbol.code)
        .join(Setup, Setup.id == TradePlan.setup_id)
        .join(Symbol, Symbol.id == TradePlan.symbol_id)
        .where(TradePlan.user_id == ctx.owner_id)
    )
    if plan_date is not None:
        stmt = stmt.where(TradePlan.plan_date == plan_date)
    if status is not None:
        stmt = stmt.where(TradePlan.status == status)
    if analysis_id is not None:
        stmt = stmt.where(TradePlan.analysis_id == analysis_id)
    if account_id is not None:
        stmt = stmt.where(TradePlan.account_id == account_id)
    stmt = stmt.order_by(TradePlan.plan_date.desc(), Symbol.code, TradePlan.scenario_label)
    rows = (await session.execute(stmt)).all()
    plans = [r[0] for r in rows]

    setup_ids = {p.setup_id for p in plans}
    items_by_setup: dict[uuid.UUID, list[SetupChecklistItem]] = defaultdict(list)
    if setup_ids:
        istmt = (
            select(SetupChecklistItem)
            .where(SetupChecklistItem.setup_id.in_(setup_ids))
            .order_by(SetupChecklistItem.position)
        )
        for item in (await session.execute(istmt)).scalars():
            items_by_setup[item.setup_id].append(item)
    answers = await _answers(session, [p.id for p in plans])

    frozen: dict[uuid.UUID, list[dict[str, Any]]] = {}
    locked_ids = [p.id for p in plans if p.current_revision > 0]
    if locked_ids:
        rstmt = select(TradePlanRevision.plan_id, TradePlanRevision.snapshot).where(
            TradePlanRevision.plan_id.in_(locked_ids), TradePlanRevision.revision_no == 1
        )
        frozen = {pid: s.get("checklist", []) for pid, s in (await session.execute(rstmt)).all()}

    out = []
    for plan, setup_name, code in rows:
        checklist = (
            _frozen_status(frozen[plan.id])
            if plan.id in frozen
            else _status(items_by_setup.get(plan.setup_id, []), answers.get(plan.id, {}))
        )
        out.append(_brief(plan, setup_name, code, checklist))
    return out


def _brief(plan: TradePlan, setup_name: str, code: str, checklist: ChecklistStatus) -> PlanBrief:
    return PlanBrief(
        id=plan.id,
        analysis_id=plan.analysis_id,
        account_id=plan.account_id,
        symbol_id=plan.symbol_id,
        symbol_code=code,
        setup_id=plan.setup_id,
        setup_name=setup_name,
        plan_date=plan.plan_date,
        scenario_label=plan.scenario_label,
        direction=plan.direction,
        entry_type=plan.entry_type,
        entry_price=plan.entry_price,
        stop_loss=plan.stop_loss,
        take_profits=_tps(plan),
        planned_risk_pct=plan.planned_risk_pct,
        planned_risk_amount=plan.planned_risk_amount,
        planned_lot=plan.planned_lot,
        planned_rr=plan.planned_rr,
        status=plan.status,
        locked_at=plan.locked_at,
        valid_until=plan.valid_until,
        checklist=checklist,
    )


async def detail(session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID) -> PlanOut:
    plan = await _get(session, ctx, plan_id)
    setup = await session.get(Setup, plan.setup_id)
    symbol = await session.get(Symbol, plan.symbol_id)
    account = await session.get(TradingAccount, plan.account_id)
    assert setup is not None and symbol is not None and account is not None
    revisions = await _revisions(session, plan.id)

    if revisions:
        frozen = revisions[0].snapshot.get("checklist", [])
        items = [
            ChecklistItemState(
                id=uuid.UUID(c["item_id"]),
                text=c["text"],
                is_required=c["is_required"],
                checked=c["checked"],
                note="",
            )
            for c in frozen
        ]
        checklist = _frozen_status(frozen)
    else:
        live = await _live_checklist(session, plan)
        items = [
            ChecklistItemState(
                id=c["item_id"],
                text=c["text"],
                is_required=c["is_required"],
                checked=c["checked"],
                note=c["note"],
            )
            for c in live
        ]
        db_items = await _items(session, plan.setup_id)
        checklist = _status(db_items, (await _answers(session, [plan.id])).get(plan.id, {}))

    calc: CalcMeta | None = None
    rrs: list[Decimal] | None = None
    try:
        result = await _calc(
            session,
            ctx,
            account,
            symbol_id=plan.symbol_id,
            direction=plan.direction,
            entry=plan.entry_price,
            stop_loss=plan.stop_loss,
            take_profits=plan.take_profits,
            rate=plan.quote_to_account_rate,
            lot=plan.planned_lot,
        )
        rrs = result.rr_per_tp
        calc = CalcMeta(
            balance=result.balance,
            currency=result.currency,
            contract_size=result.contract_size,
            value_per_point=result.value_per_point,
            tick_value_source=result.tick_value_source,
        )
    except AppError:
        calc = None

    pre = await _pre_emotion(session, plan.id)
    brief = _brief(plan, setup.name, symbol.code, checklist)
    brief.take_profits = _tps(plan, rrs)
    return PlanOut(
        **brief.model_dump(),
        quote_to_account_rate=plan.quote_to_account_rate,
        management_plan=ManagementPlan.model_validate(snap.norm_management(plan.management_plan)),
        invalidation=plan.invalidation,
        status_reason=plan.status_reason,
        status_changed_at=plan.status_changed_at,
        lock_hash=plan.lock_hash,
        triggered_at=plan.triggered_at,
        current_revision=plan.current_revision,
        current_hash=revisions[-1].snapshot_hash if revisions else None,
        currency=account.currency,
        calc=calc,
        checklist_items=items,
        pre_emotion=EmotionOut(
            mood=pre.mood,
            confidence=pre.confidence,
            tags=list(pre.tags or []),
            note=pre.note,
            logged_at=pre.logged_at,
        )
        if pre
        else None,
        revisions=[RevisionOut.model_validate(r) for r in revisions],
        can_lock=plan.status == "draft" and not checklist.missing,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


# ------------------------------------------------------------------ write (draft)


async def create(session: AsyncSession, ctx: AccessContext, body: PlanCreate) -> PlanOut:
    account = await _account(session, ctx, body.account_id)
    setup = await _setup(session, ctx, body.setup_id)
    if await session.get(Symbol, body.symbol_id) is None:
        raise NotFound("Symbol not found")
    analysis: MarketAnalysis | None = None
    if body.analysis_id is not None:
        analysis = await get_owned_or_404(session, MarketAnalysis, body.analysis_id, ctx)
        if analysis.symbol_id != body.symbol_id:
            raise AppError(
                "symbol_mismatch", "The plan's symbol differs from the analysis", status_code=422
            )
    tz = await user_zone(session, ctx)
    plan_date = body.plan_date or (analysis.analysis_date if analysis else local_today(tz))
    tps = _tps_json(body.take_profits)
    result = await _calc(
        session,
        ctx,
        account,
        symbol_id=body.symbol_id,
        direction=body.direction,
        entry=body.entry_price,
        stop_loss=body.stop_loss,
        take_profits=tps,
        rate=body.quote_to_account_rate,
        risk_pct=body.planned_risk_pct,
    )
    plan = TradePlan(
        user_id=ctx.owner_id,
        analysis_id=body.analysis_id,
        setup_id=setup.id,
        account_id=account.id,
        symbol_id=body.symbol_id,
        plan_date=plan_date,
        direction=body.direction,
        scenario_label=body.scenario_label or await _next_scenario(session, body.analysis_id),
        entry_type=body.entry_type,
        entry_price=body.entry_price,
        stop_loss=body.stop_loss,
        take_profits=tps,
        planned_risk_pct=body.planned_risk_pct,
        planned_risk_amount=result.risk_amount,
        planned_lot=result.lot,
        planned_rr=result.rr_avg,
        quote_to_account_rate=body.quote_to_account_rate,
        management_plan=body.management_plan.model_dump(),
        invalidation=body.invalidation,
        valid_until=body.valid_until or end_of_day(plan_date, tz),
        status="draft",
        status_changed_at=utcnow(),
    )
    session.add(plan)
    await session.flush()
    await _replace_answers(session, plan, body.checklist_answers)
    if body.pre_emotion is not None:
        await _set_pre_emotion(session, ctx, plan, body.pre_emotion)
    await record(
        session,
        ctx,
        action="create",
        entity="trade_plan",
        entity_id=plan.id,
        after=snap.build(plan, []),
        account_id=plan.account_id,
    )
    return await detail(session, ctx, plan.id)


async def update(
    session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID, body: PlanUpdate
) -> PlanOut:
    plan = await _get(session, ctx, plan_id)
    if plan.status != "draft":
        raise Conflict(
            "plan_not_draft", "Only a draft can be edited; a locked plan needs a revision"
        )
    before = snap.build(plan, [])
    data = body.model_dump(exclude_unset=True)
    if "setup_id" in data and data["setup_id"] not in (None, plan.setup_id):
        await _setup(session, ctx, data["setup_id"])
        plan.setup_id = data["setup_id"]
        if body.checklist_answers is None:  # answers belonged to the old setup's checklist
            await session.execute(
                delete(PlanChecklistAnswer).where(PlanChecklistAnswer.plan_id == plan.id)
            )
    for key in ("direction", "scenario_label", "entry_type", "entry_price", "stop_loss"):
        if data.get(key) is not None:
            setattr(plan, key, data[key])
    if body.take_profits is not None:
        plan.take_profits = _tps_json(body.take_profits)
    if body.planned_risk_pct is not None:
        plan.planned_risk_pct = body.planned_risk_pct
    if "quote_to_account_rate" in data:
        plan.quote_to_account_rate = body.quote_to_account_rate
    if body.management_plan is not None:
        plan.management_plan = body.management_plan.model_dump()
    if body.invalidation is not None:
        plan.invalidation = body.invalidation
    if body.valid_until is not None:
        plan.valid_until = body.valid_until

    account = await _account(session, ctx, plan.account_id)
    result = await _calc(
        session,
        ctx,
        account,
        symbol_id=plan.symbol_id,
        direction=plan.direction,
        entry=plan.entry_price,
        stop_loss=plan.stop_loss,
        take_profits=plan.take_profits,
        rate=plan.quote_to_account_rate,
        risk_pct=plan.planned_risk_pct,
    )
    plan.planned_risk_amount, plan.planned_lot, plan.planned_rr = (
        result.risk_amount,
        result.lot,
        result.rr_avg,
    )
    await session.flush()
    if body.checklist_answers is not None:
        await _replace_answers(session, plan, body.checklist_answers)
    await session.refresh(plan)
    await record(
        session,
        ctx,
        action="update",
        entity="trade_plan",
        entity_id=plan.id,
        before=before,
        after=snap.build(plan, []),
        account_id=plan.account_id,
    )
    return await detail(session, ctx, plan.id)


async def set_pre_emotion(
    session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID, body: EmotionIn
) -> PlanOut:
    plan = await _get(session, ctx, plan_id)
    if plan.status not in OPEN_STATUSES:
        raise Conflict("plan_closed", "Pre-trade emotion can only be set before the entry")
    await _set_pre_emotion(session, ctx, plan, body)
    return await detail(session, ctx, plan.id)


async def delete_plan(session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID) -> None:
    """Drafts only: a locked plan is history (skip / invalidate it instead)."""
    plan = await _get(session, ctx, plan_id)
    if plan.status != "draft":
        raise Conflict("plan_not_draft", "Only a draft can be deleted")
    before, account_id = snap.build(plan, []), plan.account_id
    await session.execute(
        delete(EmotionLog).where(EmotionLog.owner_type == "plan", EmotionLog.owner_id == plan.id)
    )
    await session.execute(
        delete(ChartDrawing).where(
            ChartDrawing.owner_type == "plan", ChartDrawing.owner_id == plan.id
        )
    )
    await session.delete(plan)
    await session.flush()
    await record(
        session,
        ctx,
        action="delete",
        entity="trade_plan",
        entity_id=plan_id,
        before=before,
        account_id=account_id,
    )


# ------------------------------------------------------------------ lock / revisions / status


async def lock(session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID) -> PlanOut:
    """F-06 AC3-AC4: required checklist items ticked → locked_at + lock_hash + revision 1."""
    plan = await _get(session, ctx, plan_id)
    if plan.status != "draft":
        raise Conflict("plan_not_draft", "Only a draft can be locked")
    checklist = await _live_checklist(session, plan)
    missing = [c for c in checklist if c["is_required"] and not c["checked"]]
    if missing:
        raise AppError(
            "checklist_incomplete",
            "Tick every required checklist item before locking",
            status_code=422,
            details={"missing": [{"id": str(c["item_id"]), "text": c["text"]} for c in missing]},
        )
    now = utcnow()
    if plan.valid_until is not None and plan.valid_until <= now:
        raise AppError("valid_until_passed", "The plan is no longer valid", status_code=422)
    snapshot = snap.build(plan, checklist)
    digest = snap.digest(snapshot)
    plan.status, plan.locked_at, plan.lock_hash = "locked", now, digest
    plan.status_changed_at, plan.current_revision = now, 1
    session.add(
        TradePlanRevision(
            plan_id=plan.id,
            revision_no=1,
            snapshot=snapshot,
            snapshot_hash=digest,
            changes={},
            reason=None,
            changed_at=now,
            changed_after_entry=False,
        )
    )
    await session.flush()
    await record(
        session,
        ctx,
        action="lock",
        entity="trade_plan",
        entity_id=plan.id,
        after={"lock_hash": digest, "revision_no": 1},
        account_id=plan.account_id,
    )
    return await detail(session, ctx, plan.id)


def _current_values(plan: TradePlan) -> dict[str, Any]:
    return {name: getattr(plan, name) for name in snap.REVISABLE}


async def revise(
    session: AsyncSession,
    ctx: AccessContext,
    plan_id: uuid.UUID,
    body: RevisionChanges,
    reason: str | None,
    *,
    dry_run: bool = False,
) -> RevisionOut:
    """F-06 AC4-AC5: append a revision with a reason; after the entry it is flagged.

    Before the entry the lot follows the (possibly new) risk %; once in the market the
    position size is fixed, so moving the SL changes the money at risk instead — that
    difference is reported as `risk_delta_*` ("Risk +0.33R (+$335)")."""
    plan = await _get(session, ctx, plan_id)
    if plan.status not in ("locked", "triggered"):
        raise Conflict("plan_not_revisable", "Only a locked or triggered plan takes revisions")
    after_entry = plan.status == "triggered"
    if not dry_run and not reason:
        raise AppError("reason_required", "A revision needs a reason", status_code=422)
    changes = body.model_dump(exclude_unset=True)
    if "take_profits" in changes and body.take_profits is not None:
        changes["take_profits"] = _tps_json(body.take_profits)
    if after_entry and "planned_risk_pct" in changes:
        raise AppError(
            "risk_pct_after_entry",
            "The position is open: move the SL or TP instead of the risk %",
            status_code=422,
        )
    current = _current_values(plan)
    new = {**current, **{k: v for k, v in changes.items() if v is not None or k == "valid_until"}}
    diff = {
        name: {"from": snap.norm_field(name, current[name]), "to": snap.norm_field(name, new[name])}
        for name in snap.REVISABLE
        if snap.norm_field(name, current[name]) != snap.norm_field(name, new[name])
    }
    if not diff:
        raise AppError("no_changes", "The revision changes nothing", status_code=422)

    account = await session.get(TradingAccount, plan.account_id)
    assert account is not None
    result = await _calc(
        session,
        ctx,
        account,
        symbol_id=plan.symbol_id,
        direction=plan.direction,
        entry=new["entry_price"],
        stop_loss=new["stop_loss"],
        take_profits=new["take_profits"],
        rate=plan.quote_to_account_rate,
        **({"lot": plan.planned_lot} if after_entry else {"risk_pct": new["planned_risk_pct"]}),
    )
    delta = result.risk_amount - plan.planned_risk_amount
    delta_r = (
        (delta / plan.planned_risk_amount).quantize(CENT) if plan.planned_risk_amount else None
    )
    now = utcnow()
    revision_no = plan.current_revision + 1

    first = (await _revisions(session, plan.id))[0]
    if dry_run:
        return RevisionOut(
            id=None,
            revision_no=revision_no,
            snapshot_hash="",
            changes=diff,
            risk_delta_amount=delta,
            risk_delta_r=delta_r,
            reason=reason,
            changed_at=now,
            changed_after_entry=after_entry,
        )

    for name in snap.REVISABLE:
        setattr(plan, name, new[name])
    plan.planned_risk_amount, plan.planned_lot, plan.planned_rr = (
        result.risk_amount,
        result.lot,
        result.rr_avg,
    )
    plan.current_revision = revision_no
    await session.flush()
    await session.refresh(plan)
    snapshot = snap.build(plan, first.snapshot.get("checklist", []))
    revision = TradePlanRevision(
        plan_id=plan.id,
        revision_no=revision_no,
        snapshot=snapshot,
        snapshot_hash=snap.digest(snapshot),
        changes=diff,
        risk_delta_amount=delta,
        risk_delta_r=delta_r,
        reason=reason,
        changed_at=now,
        changed_after_entry=after_entry,
    )
    session.add(revision)
    await session.flush()
    await record(
        session,
        ctx,
        action="revise",
        entity="trade_plan",
        entity_id=plan.id,
        after={"revision_no": revision_no, "changes": diff, "reason": reason},
        account_id=plan.account_id,
    )
    return RevisionOut.model_validate(revision)


async def list_revisions(
    session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID
) -> list[RevisionOut]:
    plan = await _get(session, ctx, plan_id)
    return [RevisionOut.model_validate(r) for r in await _revisions(session, plan.id)]


async def set_status(
    session: AsyncSession, ctx: AccessContext, plan_id: uuid.UUID, body: StatusIn
) -> PlanOut:
    """F-06 AC6: skipped / missed / invalidated, always with a reason."""
    plan = await _get(session, ctx, plan_id)
    allowed = MANUAL_TRANSITIONS[body.status]
    if plan.status not in allowed:
        raise AppError(
            "invalid_transition",
            f"Cannot change a {plan.status} plan to {body.status}",
            status_code=409,
            details={"from": plan.status, "to": body.status, "allowed_from": list(allowed)},
        )
    before = plan.status
    plan.status, plan.status_reason, plan.status_changed_at = body.status, body.reason, utcnow()
    await session.flush()
    await record(
        session,
        ctx,
        action="status",
        entity="trade_plan",
        entity_id=plan.id,
        before={"status": before},
        after={"status": body.status, "reason": body.reason},
        account_id=plan.account_id,
    )
    return await detail(session, ctx, plan.id)


async def mark_triggered(session: AsyncSession, plan: TradePlan, at: datetime) -> None:
    """Called by matching (Phase 4) when a position is linked to a locked plan."""
    if plan.status != "locked":
        raise Conflict("plan_not_locked", "Only a locked plan can be triggered")
    plan.status, plan.triggered_at, plan.status_changed_at = "triggered", at, utcnow()
    await session.flush()


# Statuses a plan moves between as positions link to it / close / unlink.
TRADE_DRIVEN = ("locked", "triggered", "closed", "expired", "missed")


async def sync_with_positions(session: AsyncSession, plan_id: uuid.UUID) -> TradePlan | None:
    """Plan status from its linked trades (spec §1.7): any trade → triggered, all closed →
    closed, none any more → back to locked (or expired once `valid_until` has passed).

    Only trades that count as planned (locked before their entry, F-07 AC3) drive the status;
    drafts and skipped / invalidated plans are left alone."""
    from app.modules.positions.models import Position

    plan = await session.get(TradePlan, plan_id, with_for_update=True)
    if plan is None or plan.locked_at is None or plan.status not in TRADE_DRIVEN:
        return plan
    rows = (
        await session.execute(
            select(Position.status, Position.opened_at).where(
                Position.plan_id == plan.id, Position.is_unplanned.is_(False)
            )
        )
    ).all()
    now = utcnow()
    if rows:
        status = "closed" if all(r.status == "closed" for r in rows) else "triggered"
        triggered_at = min(r.opened_at for r in rows)
    else:
        if plan.status not in ("triggered", "closed"):
            return plan
        expired = plan.valid_until is not None and plan.valid_until < now
        status, triggered_at = ("expired" if expired else "locked"), None
    if (plan.status, plan.triggered_at) != (status, triggered_at):
        plan.status, plan.triggered_at, plan.status_changed_at = status, triggered_at, now
        await session.flush()
    return plan


async def expire_due(session: AsyncSession, now: datetime | None = None) -> int:
    """F-06 AC6: drafts and locked plans past `valid_until` without a trade → expired.

    Triggered plans have a trade, so they are never expired."""
    now = now or utcnow()
    stmt = (
        sa_update(TradePlan)
        .where(
            TradePlan.status.in_(OPEN_STATUSES),
            TradePlan.valid_until.is_not(None),
            TradePlan.valid_until < now,
        )
        .values(status="expired", status_reason="valid_until_passed", status_changed_at=now)
        .returning(TradePlan.id)
    )
    return len((await session.execute(stmt)).all())
