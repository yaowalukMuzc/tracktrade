"""Accounts business rules (F-02, F-03 AC2). Every change of an account, its risk profile,
rules or symbol mapping is written to the audit log."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext, get_owned_or_404
from app.core.errors import Conflict, NotFound
from app.modules.accounts.models import (
    RISK_DEFAULTS,
    RISK_FIELDS,
    AccountSymbolOverride,
    RiskProfile,
    RiskProfileVersion,
    TradingAccount,
    TradingRule,
)
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountUpdate,
    RiskProfileIn,
    RiskStatusOut,
    RuleCreate,
    RuleUpdate,
    SymbolOverrideIn,
    SymbolOverrideOut,
    SymbolResolveOut,
    Usage,
    _validate_params,
)
from app.modules.audit.service import record, snapshot
from app.modules.positions.models import Position
from app.modules.symbols.models import Symbol
from app.modules.users.models import User

CENT = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ accounts


async def list_accounts(
    session: AsyncSession, ctx: AccessContext, *, include_archived: bool = False
) -> Sequence[TradingAccount]:
    stmt = select(TradingAccount).where(TradingAccount.user_id == ctx.owner_id)
    if not include_archived:
        stmt = stmt.where(TradingAccount.is_active.is_(True))
    stmt = stmt.order_by(TradingAccount.is_active.desc(), TradingAccount.created_at)
    return (await session.execute(stmt)).scalars().all()


async def get_account(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> TradingAccount:
    return await get_owned_or_404(session, TradingAccount, account_id, ctx)


async def create_account(
    session: AsyncSession, ctx: AccessContext, body: AccountCreate
) -> TradingAccount:
    data = body.model_dump(exclude={"risk_profile"})
    account = TradingAccount(user_id=ctx.owner_id, **data)
    session.add(account)
    await session.flush()
    await record(
        session,
        ctx,
        action="create",
        entity="trading_account",
        entity_id=account.id,
        after=snapshot(account),
        account_id=account.id,
    )
    values = body.risk_profile.model_dump() if body.risk_profile else dict(RISK_DEFAULTS)
    await _create_risk_profile(session, ctx, account, values)
    return account


async def update_account(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, patch: AccountUpdate
) -> TradingAccount:
    account = await get_account(session, ctx, account_id)
    before = snapshot(account)
    for field, value in patch.model_dump(exclude_unset=True).items():
        if value is not None or field == "account_number":
            setattr(account, field, value)
    await session.flush()
    await record(
        session,
        ctx,
        action="update",
        entity="trading_account",
        entity_id=account.id,
        before=before,
        after=snapshot(account),
        account_id=account.id,
    )
    return account


async def set_archived(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, archived: bool
) -> TradingAccount:
    account = await get_account(session, ctx, account_id)
    if account.is_active == (not archived):
        return account
    before = snapshot(account)
    account.is_active = not archived
    account.archived_at = _now() if archived else None
    await session.flush()
    await record(
        session,
        ctx,
        action="archive" if archived else "unarchive",
        entity="trading_account",
        entity_id=account.id,
        before=before,
        after=snapshot(account),
        account_id=account.id,
    )
    return account


# ------------------------------------------------------------------ risk profile


async def _create_risk_profile(
    session: AsyncSession, ctx: AccessContext, account: TradingAccount, values: dict[str, Any]
) -> RiskProfile:
    profile = RiskProfile(account_id=account.id, version=1, **values)
    session.add(profile)
    session.add(RiskProfileVersion(account_id=account.id, version=1, valid_from=_now(), **values))
    await session.flush()
    await record(
        session,
        ctx,
        action="create",
        entity="risk_profile",
        entity_id=profile.id,
        after=snapshot(profile),
        account_id=account.id,
    )
    return profile


async def get_risk_profile(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> RiskProfile:
    await get_account(session, ctx, account_id)
    stmt = select(RiskProfile).where(RiskProfile.account_id == account_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if profile is None:  # every account gets one at creation; guard anyway
        raise NotFound("Risk profile not found")
    return profile


async def update_risk_profile(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, body: RiskProfileIn
) -> RiskProfile:
    """New limits apply from now on; a new version row keeps the old ones for older trades."""
    profile = await get_risk_profile(session, ctx, account_id)
    values = body.model_dump()
    if all(getattr(profile, k) == v for k, v in values.items()):
        return profile
    before = snapshot(profile)
    for key, value in values.items():
        setattr(profile, key, value)
    profile.version += 1
    session.add(
        RiskProfileVersion(
            account_id=account_id, version=profile.version, valid_from=_now(), **values
        )
    )
    await session.flush()
    await session.refresh(profile)
    await record(
        session,
        ctx,
        action="update",
        entity="risk_profile",
        entity_id=profile.id,
        before=before,
        after=snapshot(profile),
        account_id=account_id,
    )
    return profile


async def list_risk_profile_versions(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> Sequence[RiskProfileVersion]:
    await get_account(session, ctx, account_id)
    stmt = (
        select(RiskProfileVersion)
        .where(RiskProfileVersion.account_id == account_id)
        .order_by(RiskProfileVersion.version.desc())
    )
    return (await session.execute(stmt)).scalars().all()


async def risk_profile_at(
    session: AsyncSession, account_id: uuid.UUID, at: datetime
) -> RiskProfileVersion | None:
    """The limits in force at `at` — what a trade opened then is judged against (F-02 AC4)."""
    stmt = (
        select(RiskProfileVersion)
        .where(RiskProfileVersion.account_id == account_id, RiskProfileVersion.valid_from <= at)
        .order_by(RiskProfileVersion.version.desc())
        .limit(1)
    )
    version = (await session.execute(stmt)).scalar_one_or_none()
    if version is None:  # trade imported from before the account existed in TrackTrade
        stmt = (
            select(RiskProfileVersion)
            .where(RiskProfileVersion.account_id == account_id)
            .order_by(RiskProfileVersion.version)
            .limit(1)
        )
        version = (await session.execute(stmt)).scalar_one_or_none()
    return version


async def current_balance(session: AsyncSession, account: TradingAccount) -> Decimal:
    """Broker-reported balance when a connection sends it (PLAN M26), else initial + closed P/L."""
    if account.last_balance is not None:
        return account.last_balance
    closed = await session.scalar(
        select(func.coalesce(func.sum(Position.net_pnl), 0)).where(
            Position.account_id == account.id, Position.status == "closed"
        )
    )
    return account.initial_balance + Decimal(closed or 0)


async def _day_bounds(session: AsyncSession, ctx: AccessContext) -> tuple[datetime, datetime]:
    """Today in the trader's timezone, as UTC instants (PLAN Q6: per-account zone later)."""
    user = await session.get(User, ctx.owner_id)
    try:
        tz = ZoneInfo(user.timezone if user else "UTC")
    except (KeyError, ValueError):
        tz = ZoneInfo("UTC")
    start = datetime.combine(datetime.now(tz).date(), time.min, tzinfo=tz)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


async def _peak_balance(session: AsyncSession, account: TradingAccount) -> Decimal:
    """Highest balance reached: initial balance + running sum of closed P/L, in close order."""
    running = (
        func.sum(Position.net_pnl).over(order_by=(Position.closed_at, Position.id)).label("running")
    )
    sub = (
        select(running)
        .where(Position.account_id == account.id, Position.status == "closed")
        .subquery()
    )
    best = await session.scalar(select(func.max(sub.c.running)))
    return account.initial_balance + max(Decimal(best or 0), Decimal(0))


async def risk_status(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> RiskStatusOut:
    """Today's use of the limits from real trades (F-02 + Accounts "today" card)."""
    account = await get_account(session, ctx, account_id)
    profile = await get_risk_profile(session, ctx, account_id)
    balance = await current_balance(session, account)
    equity = account.last_equity if account.last_equity is not None else balance
    start, end = await _day_bounds(session, ctx)
    closed_today = await session.scalar(
        select(func.coalesce(func.sum(Position.net_pnl), 0)).where(
            Position.account_id == account_id,
            Position.status == "closed",
            Position.closed_at >= start,
            Position.closed_at < end,
        )
    )
    opened_today = await session.scalar(
        select(func.count()).where(
            Position.account_id == account_id,
            Position.opened_at >= start,
            Position.opened_at < end,
        )
    )
    peak = max(await _peak_balance(session, account), balance)
    drawdown = ((peak - balance) / peak * 100).quantize(CENT) if peak > 0 else Decimal(0)
    # Daily limit is a % of the balance at the start of the day (FTMO style).
    day_start_balance = balance - Decimal(closed_today or 0)
    daily_limit = (day_start_balance * profile.max_daily_loss_pct / 100).quantize(CENT)
    return RiskStatusOut(
        currency=account.currency,
        balance=balance,
        equity=equity,
        daily_loss=Usage(used=max(-Decimal(closed_today or 0), Decimal(0)), limit=daily_limit),
        drawdown_pct=Usage(used=max(drawdown, Decimal(0)), limit=profile.max_drawdown_pct),
        trades_today=Usage(
            used=Decimal(opened_today or 0), limit=Decimal(profile.max_trades_per_day)
        ),
    )


def risk_values(source: RiskProfile | RiskProfileVersion) -> dict[str, Any]:
    return {key: getattr(source, key) for key in RISK_FIELDS}


# ------------------------------------------------------------------ rules


async def list_rules(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> Sequence[TradingRule]:
    await get_account(session, ctx, account_id)
    stmt = (
        select(TradingRule)
        .where(TradingRule.account_id == account_id)
        .order_by(TradingRule.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


async def _get_rule(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, rule_id: uuid.UUID
) -> TradingRule:
    await get_account(session, ctx, account_id)
    stmt = select(TradingRule).where(
        TradingRule.id == rule_id, TradingRule.account_id == account_id
    )
    rule = (await session.execute(stmt)).scalar_one_or_none()
    if rule is None:
        raise NotFound()
    return rule


async def create_rule(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, body: RuleCreate
) -> TradingRule:
    await get_account(session, ctx, account_id)
    rule = TradingRule(
        account_id=account_id,
        created_by="trader",
        created_by_user_id=ctx.user_id,
        **body.model_dump(),
    )
    session.add(rule)
    await session.flush()
    await session.refresh(rule)
    await record(
        session,
        ctx,
        action="create",
        entity="trading_rule",
        entity_id=rule.id,
        after=snapshot(rule),
        account_id=account_id,
    )
    return rule


async def update_rule(
    session: AsyncSession,
    ctx: AccessContext,
    account_id: uuid.UUID,
    rule_id: uuid.UUID,
    patch: RuleUpdate,
) -> TradingRule:
    rule = await _get_rule(session, ctx, account_id, rule_id)
    before = snapshot(rule)
    data = patch.model_dump(exclude_unset=True, exclude_none=True)
    if "params" in data:
        data["params"] = _validate_params(rule.code, data["params"])
    for key, value in data.items():
        setattr(rule, key, value)
    await session.flush()
    await record(
        session,
        ctx,
        action="update",
        entity="trading_rule",
        entity_id=rule.id,
        before=before,
        after=snapshot(rule),
        account_id=account_id,
    )
    return rule


async def delete_rule(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, rule_id: uuid.UUID
) -> None:
    rule = await _get_rule(session, ctx, account_id, rule_id)
    before = snapshot(rule)
    await session.delete(rule)
    await session.flush()
    await record(
        session,
        ctx,
        action="delete",
        entity="trading_rule",
        entity_id=rule_id,
        before=before,
        account_id=account_id,
    )


# ------------------------------------------------------------------ symbol overrides


def _override_out(row: AccountSymbolOverride, symbol: Symbol) -> SymbolOverrideOut:
    return SymbolOverrideOut(
        id=row.id,
        broker_symbol=row.broker_symbol,
        symbol_id=row.symbol_id,
        symbol_code=symbol.code,
        contract_size=row.contract_size,
        tick_value=row.tick_value,
    )


async def list_overrides(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID
) -> list[SymbolOverrideOut]:
    await get_account(session, ctx, account_id)
    stmt = (
        select(AccountSymbolOverride, Symbol)
        .join(Symbol, Symbol.id == AccountSymbolOverride.symbol_id)
        .where(AccountSymbolOverride.account_id == account_id)
        .order_by(AccountSymbolOverride.broker_symbol)
    )
    return [_override_out(o, s) for o, s in (await session.execute(stmt)).all()]


async def upsert_override(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, body: SymbolOverrideIn
) -> SymbolOverrideOut:
    """Create or replace the mapping of one broker symbol (unique per account)."""
    await get_account(session, ctx, account_id)
    symbol = await session.get(Symbol, body.symbol_id)
    if symbol is None:
        raise NotFound("Symbol not found")
    stmt = select(AccountSymbolOverride).where(
        AccountSymbolOverride.account_id == account_id,
        func.upper(AccountSymbolOverride.broker_symbol) == body.broker_symbol.upper(),
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    before = snapshot(row) if row else None
    if row is None:
        row = AccountSymbolOverride(account_id=account_id, **body.model_dump())
        session.add(row)
    else:
        for key, value in body.model_dump().items():
            setattr(row, key, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise Conflict("symbol_override_exists", "This broker symbol is already mapped") from exc
    await record(
        session,
        ctx,
        action="update" if before else "create",
        entity="account_symbol_override",
        entity_id=row.id,
        before=before,
        after=snapshot(row),
        account_id=account_id,
    )
    return _override_out(row, symbol)


async def delete_override(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, override_id: uuid.UUID
) -> None:
    await get_account(session, ctx, account_id)
    stmt = select(AccountSymbolOverride).where(
        AccountSymbolOverride.id == override_id, AccountSymbolOverride.account_id == account_id
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFound()
    before = snapshot(row)
    await session.delete(row)
    await session.flush()
    await record(
        session,
        ctx,
        action="delete",
        entity="account_symbol_override",
        entity_id=override_id,
        before=before,
        account_id=account_id,
    )


def _strip_suffix(broker_symbol: str) -> str:
    """`XAUUSD.m` / `EURUSDpro` / `GBPJPY-ECN` → the 6-letter standard code guess."""
    letters = "".join(ch for ch in broker_symbol.upper() if ch.isalpha())
    return letters[:6]


async def resolve_broker_symbol(
    session: AsyncSession, account_id: uuid.UUID, broker_symbol: str
) -> tuple[Symbol, AccountSymbolOverride | None] | None:
    """Broker symbol → standard symbol: the account's mapping first, then the standard code,
    then the code with the broker suffix removed (`XAUUSD.m` → XAUUSD). None when unknown."""
    stmt = (
        select(AccountSymbolOverride, Symbol)
        .join(Symbol, Symbol.id == AccountSymbolOverride.symbol_id)
        .where(
            AccountSymbolOverride.account_id == account_id,
            func.upper(AccountSymbolOverride.broker_symbol) == broker_symbol.upper(),
        )
    )
    found = (await session.execute(stmt)).first()
    if found is not None:
        row, symbol = found
        return symbol, row
    for code in dict.fromkeys((broker_symbol.upper(), _strip_suffix(broker_symbol))):
        std = (
            await session.execute(select(Symbol).where(Symbol.code == code))
        ).scalar_one_or_none()
        if std is not None:
            return std, None
    return None


async def resolve_symbol(
    session: AsyncSession, ctx: AccessContext, account_id: uuid.UUID, broker_symbol: str
) -> SymbolResolveOut:
    """Broker symbol → standard symbol + effective specs (used by the mapping UI and imports)."""
    await get_account(session, ctx, account_id)
    found = await resolve_broker_symbol(session, account_id, broker_symbol)
    if found is None:
        raise NotFound("Unknown symbol; add a symbol mapping for this account")
    symbol, row = found
    return SymbolResolveOut(
        broker_symbol=broker_symbol,
        symbol_id=symbol.id,
        symbol_code=symbol.code,
        contract_size=(row.contract_size if row else None) or symbol.contract_size,
        tick_value=row.tick_value if row else None,
        source="override" if row else "standard",
    )
