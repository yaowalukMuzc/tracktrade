"""`POST /risk/calc` — lot ↔ risk amount ↔ R:R for an account and symbol (F-03 AC3, F-06 AC2)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import AccessContext
from app.core.db import get_session
from app.modules.accounts import service as accounts
from app.modules.auth.deps import get_access_context
from app.modules.risk.calculator import TakeProfit
from app.modules.risk.service import RiskCalcOut, compute

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


@router.post("/calc", response_model=RiskCalcOut)
async def risk_calc(
    body: RiskCalcIn,
    ctx: AccessContext = Depends(get_access_context),
    session: AsyncSession = Depends(get_session),
) -> RiskCalcOut:
    account = await accounts.get_account(session, ctx, body.account_id)
    return await compute(
        session,
        ctx,
        account,
        symbol_id=body.symbol_id,
        direction=body.direction,
        entry=body.entry,
        stop_loss=body.stop_loss,
        take_profits=[TakeProfit(tp.price, tp.pct) for tp in body.take_profits],
        risk_pct=body.risk_pct,
        lot=body.lot,
        quote_to_account_rate=body.quote_to_account_rate,
    )
