"""Lot / risk / R:R for an account and symbol — shared by `/risk/calc` and trade plans."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.errors import AppError, NotFound
from app.modules.accounts import service as accounts
from app.modules.accounts.models import AccountSymbolOverride, TradingAccount
from app.modules.risk.calculator import (
    CalcInput,
    RiskInputError,
    SymbolSpec,
    TakeProfit,
    calculate,
)
from app.modules.symbols.models import Symbol


class RiskCalcOut(BaseModel):
    balance: Decimal
    currency: str
    lot: Decimal
    risk_amount: Decimal
    risk_pct: Decimal
    target_risk_amount: Decimal | None
    value_per_point: Decimal
    sl_points: Decimal
    rr_per_tp: list[Decimal]
    rr_avg: Decimal | None
    contract_size: Decimal
    tick_value_source: Literal["override", "standard"]


async def symbol_spec(session: AsyncSession, account: TradingAccount, symbol: Symbol) -> SymbolSpec:
    """Standard spec refined by the account's broker override (contract size / tick value)."""
    # Any broker name of this symbol on the account (XAUUSD.m, XAUUSD) — prefer one with MT5 specs.
    override = (
        await session.execute(
            select(AccountSymbolOverride)
            .where(
                AccountSymbolOverride.account_id == account.id,
                AccountSymbolOverride.symbol_id == symbol.id,
            )
            .order_by(func.coalesce(AccountSymbolOverride.tick_value, 0).desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return SymbolSpec(
        code=symbol.code,
        contract_size=(override.contract_size if override else None) or symbol.contract_size,
        point_size=symbol.point_size,
        base_currency=symbol.base_currency,
        quote_currency=symbol.quote_currency,
        tick_value=override.tick_value if override else None,
    )


async def compute(
    session: AsyncSession,
    ctx: AccessContext,
    account: TradingAccount,
    *,
    symbol_id: uuid.UUID,
    direction: Literal["long", "short"],
    entry: Decimal,
    stop_loss: Decimal,
    take_profits: Sequence[TakeProfit],
    risk_pct: Decimal | None = None,
    lot: Decimal | None = None,
    quote_to_account_rate: Decimal | None = None,
) -> RiskCalcOut:
    """Shared by `/risk/calc` and trade plans (F-06 AC2). Neither risk_pct nor lot → profile %."""
    symbol = await session.get(Symbol, symbol_id)
    if symbol is None:
        raise NotFound("Symbol not found")
    spec = await symbol_spec(session, account, symbol)
    contract_size, tick_value = spec.contract_size, spec.tick_value
    if risk_pct is None and lot is None:
        risk_pct = (await accounts.get_risk_profile(session, ctx, account.id)).risk_per_trade_pct
    balance = await accounts.current_balance(session, account)
    try:
        result = calculate(
            CalcInput(
                spec=spec,
                account_currency=account.currency,
                balance=balance,
                direction=direction,
                entry=entry,
                stop_loss=stop_loss,
                take_profits=list(take_profits),
                risk_pct=risk_pct,
                lot=lot,
                quote_to_account_rate=quote_to_account_rate,
            )
        )
    except RiskInputError as exc:
        raise AppError(exc.code, str(exc), status_code=422, details=exc.details) from exc
    return RiskCalcOut(
        balance=balance,
        currency=account.currency,
        lot=result.lot,
        risk_amount=result.risk_amount,
        risk_pct=result.risk_pct,
        target_risk_amount=result.target_risk_amount,
        value_per_point=result.value_per_point,
        sl_points=result.sl_points,
        rr_per_tp=result.rr_per_tp,
        rr_avg=result.rr_avg,
        contract_size=contract_size,
        tick_value_source="override" if tick_value is not None else "standard",
    )
