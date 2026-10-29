"""`/today` (Today page) and `/daily/{date}` (daily mood, F-11 AC5)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AfterValidator, BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.accounts import service as accounts
from app.modules.accounts.schemas import RiskStatusOut
from app.modules.analysis import service as analyses
from app.modules.analysis.schemas import AnalysisSummary
from app.modules.auth.deps import get_access_context
from app.modules.emotions.models import EmotionLog
from app.modules.plans import service as plans
from app.modules.plans.schemas import PlanBrief
from app.modules.positions import service as positions

router = APIRouter(tags=["today"])

Ctx = Depends(get_access_context)
Db = Depends(get_session)


class DailyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mood: Annotated[int, Field(ge=1, le=10)] | None = None
    tags: Annotated[list[uuid.UUID], Field(max_length=12)] = []
    note: Annotated[str, Field(max_length=2000), AfterValidator(str.strip)] = ""


class DailyOut(BaseModel):
    date: date
    mood: int | None
    tags: list[uuid.UUID]
    note: str
    logged_at: datetime | None


class AccountRisk(RiskStatusOut):
    account_id: uuid.UUID
    name: str


class Todo(BaseModel):
    """Work waiting for the trader: trades to match (F-10), to review (F-12), inbox (Phase 5)."""

    pending_match: int = 0
    pending_review: int = 0
    inbox: int = 0


class PnlToday(BaseModel):
    """P/L of trades closed today, per account currency."""

    currency: str
    amount: Decimal
    r: Decimal
    trades: int


class TodayOut(BaseModel):
    date: date
    timezone: str
    analyses: list[AnalysisSummary]
    plans: list[PlanBrief]
    risk: list[AccountRisk]  # active accounts (or the selected one)
    pnl: list[PnlToday]
    adherence_week: Decimal | None  # Phase 6
    goal_adherence: Decimal | None  # mentor goal, Phase 8
    todo: Todo
    daily: DailyOut | None


async def _daily(session: AsyncSession, ctx: AccessContext, day: date) -> EmotionLog | None:
    stmt = select(EmotionLog).where(
        EmotionLog.user_id == ctx.owner_id,
        EmotionLog.phase == "daily",
        EmotionLog.log_date == day,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _daily_out(day: date, log: EmotionLog | None) -> DailyOut:
    if log is None:
        return DailyOut(date=day, mood=None, tags=[], note="", logged_at=None)
    return DailyOut(
        date=day,
        mood=log.mood,
        tags=list(log.tags or []),
        note=log.note,
        logged_at=log.logged_at,
    )


@router.get("/today", response_model=TodayOut)
async def today(
    day: date | None = Query(None, alias="date"),
    account_id: uuid.UUID | None = None,
    ctx: AccessContext = Ctx,
    session: AsyncSession = Db,
) -> TodayOut:
    """Today's analyses + plans, limits used and pending work; `account_id` filters (F-02 AC3)."""
    tz = await plans.user_zone(session, ctx)
    day = day or plans.local_today(tz)
    if account_id is not None:
        selected = [await accounts.get_account(session, ctx, account_id)]
    else:
        selected = list(await accounts.list_accounts(session, ctx))
    risk = [
        AccountRisk(
            **(await accounts.risk_status(session, ctx, a.id)).model_dump(),
            account_id=a.id,
            name=a.name,
        )
        for a in selected
    ]
    log = await _daily(session, ctx, day)
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)
    closed = await positions.closed_between(
        session, ctx, start, start + timedelta(days=1), account_id
    )
    return TodayOut(
        date=day,
        timezone=str(tz),
        analyses=await analyses.list_analyses(session, ctx, on=day, account_id=account_id),
        plans=await plans.briefs(session, ctx, plan_date=day, account_id=account_id),
        risk=risk,
        pnl=[PnlToday(currency=c, amount=net, r=r, trades=n) for c, net, r, n in closed],
        adherence_week=None,
        goal_adherence=None,
        todo=Todo(
            pending_match=await positions.pending_match_count(session, ctx, account_id),
            pending_review=await positions.pending_review_count(session, ctx, account_id),
        ),
        daily=_daily_out(day, log) if log else None,
    )


@router.get("/daily/{day}", response_model=DailyOut)
async def get_daily(day: date, ctx: AccessContext = Ctx, session: AsyncSession = Db) -> DailyOut:
    return _daily_out(day, await _daily(session, ctx, day))


@router.put("/daily/{day}", response_model=DailyOut)
async def put_daily(
    day: date, body: DailyIn, ctx: AccessContext = Ctx, session: AsyncSession = Db
) -> DailyOut:
    """Optional daily mood (F-11 AC5); one entry per local day, replaced on edit."""
    tags = list(dict.fromkeys(body.tags))
    await plans.validate_tags(session, ctx, tags)
    log = await _daily(session, ctx, day)
    if log is None:
        log = EmotionLog(
            user_id=ctx.owner_id,
            owner_type="day",
            owner_id=ctx.owner_id,
            phase="daily",
            log_date=day,
        )
        session.add(log)
    log.mood, log.tags, log.note, log.logged_at = body.mood, tags, body.note, datetime.now(UTC)
    await session.flush()
    return _daily_out(day, log)
