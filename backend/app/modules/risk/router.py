"""`POST /risk/calc` — lot ↔ risk amount ↔ R:R for an account and symbol (F-03 AC3, F-06 AC2)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.core.errors import AppError, NotFound
from app.modules.accounts import service as accounts
from app.modules.accounts.models import AccountSymbolOverride
from app.modules.auth.deps import get_access_context
from app.modules.risk.calculator import (
    CalcInput,
    RiskInputError,
    SymbolSpec,
    TakeProfit,
    calculate,
)
from app.modules.symbols.models import Symbol

router = APIRouter(prefix="/risk", tags=["risk"])

PriceIn = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]


class TakeProfitIn(BaseModel):
    price: PriceIn
    pct: Annotated[Decimal, Field(gt=0, le=100)] = Decimal(100)


class RiskCalcIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: uuid.UUID
    symbol_id: uuid.UUID
    direction: Literal["long", "short"]
    entry: PriceIn
    stop_loss: PriceIn
    take_profits: Annotated[list[TakeProfitIn], Field(max_length=5)] = []
    # Neither given → the account's risk profile risk %.
    risk_pct: Annotated[Decimal, Field(gt=0, le=100)] | None = None
    lot: Annotated[Decimal, Field(gt=0, le=1000)] | None = None
    quote_to_account_rate: Annotated[Decimal, Field(gt=0)] | None = None


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


@router.post("/calc", response_model=RiskCalcOut)
async def risk_calc(
    body: RiskCalcIn,
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> RiskCalcOut:
    account = await accounts.get_account(session, ctx, body.account_id)
    symbol = await session.get(Symbol, body.symbol_id)
    if symbol is None:
        raise NotFound("Symbol not found")
    # A broker override for this symbol (any broker name) refines contract size / tick value.
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
    contract_size = (override.contract_size if override else None) or symbol.contract_size
    tick_value = override.tick_value if override else None
    spec = SymbolSpec(
        code=symbol.code,
        contract_size=contract_size,
        point_size=symbol.point_size,
        base_currency=symbol.base_currency,
        quote_currency=symbol.quote_currency,
        tick_value=tick_value,
    )
    risk_pct = body.risk_pct
    if risk_pct is None and body.lot is None:
        risk_pct = (await accounts.get_risk_profile(session, ctx, account.id)).risk_per_trade_pct
    # Balance = initial balance until trades exist (Phase 4 switches to the running balance).
    balance = account.initial_balance
    try:
        result = calculate(
            CalcInput(
                spec=spec,
                account_currency=account.currency,
                balance=balance,
                direction=body.direction,
                entry=body.entry,
                stop_loss=body.stop_loss,
                take_profits=[TakeProfit(tp.price, tp.pct) for tp in body.take_profits],
                risk_pct=risk_pct,
                lot=body.lot,
                quote_to_account_rate=body.quote_to_account_rate,
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
