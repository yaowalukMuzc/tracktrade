"""Position-size / risk / R:R maths (F-03 AC3, F-06 AC2). Pure functions — no DB, no I/O.

MT5's profit formula for Forex and CFD symbols is

    profit = (close - open) * contract_size * lots * (quote → account rate)

so the money value of a 1-unit price move for 1 lot is `contract_size * rate`.
A broker override (`tick_value`, MT5 SYMBOL_TRADE_TICK_VALUE for a tick of one
`point`) replaces that product when known. The quote → account rate is
  1            when the quote currency is the account currency (EURUSD on USD),
  1 / entry    when the base currency is the account currency (USDJPY on USD),
  given        otherwise (GBPJPY on USD needs USDJPY) — `ConversionRateRequired`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Literal

Direction = Literal["long", "short"]
CENT = Decimal("0.01")


class RiskInputError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


class ConversionRateRequired(RiskInputError):
    def __init__(self, quote: str, account: str) -> None:
        super().__init__(
            "conversion_rate_required",
            f"Need the {quote}→{account} rate to value this symbol in {account}",
            {"from": quote, "to": account},
        )


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    code: str
    contract_size: Decimal
    point_size: Decimal
    base_currency: str
    quote_currency: str
    tick_value: Decimal | None = None  # account currency per point per lot (broker override)
    lot_step: Decimal = Decimal("0.01")
    min_lot: Decimal = Decimal("0.01")
    max_lot: Decimal = Decimal("100")


@dataclass(frozen=True, slots=True)
class TakeProfit:
    price: Decimal
    pct: Decimal = Decimal("100")  # share of the position closed there


@dataclass(frozen=True, slots=True)
class CalcInput:
    spec: SymbolSpec
    account_currency: str
    balance: Decimal
    direction: Direction
    entry: Decimal
    stop_loss: Decimal
    take_profits: Sequence[TakeProfit] = field(default_factory=tuple)
    risk_pct: Decimal | None = None  # size the position from risk …
    lot: Decimal | None = None  # … or value a given lot
    quote_to_account_rate: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CalcResult:
    lot: Decimal
    risk_amount: Decimal  # money lost at SL with `lot`
    risk_pct: Decimal  # of balance
    target_risk_amount: Decimal | None  # requested risk before lot rounding
    value_per_point: Decimal  # money per 1 point move, 1 lot
    sl_points: Decimal
    rr_per_tp: list[Decimal]
    rr_avg: Decimal | None  # weighted by each TP's pct


def quote_rate(
    spec: SymbolSpec, account_currency: str, entry: Decimal, given: Decimal | None
) -> Decimal:
    if given is not None:
        return given
    if spec.quote_currency == account_currency:
        return Decimal(1)
    if spec.base_currency == account_currency:
        return Decimal(1) / entry
    raise ConversionRateRequired(spec.quote_currency, account_currency)


def value_per_price_unit(
    spec: SymbolSpec, account_currency: str, entry: Decimal, given_rate: Decimal | None = None
) -> Decimal:
    """Money (account currency) per 1.0 price move for 1 lot."""
    if spec.tick_value is not None:
        return spec.tick_value / spec.point_size
    return spec.contract_size * quote_rate(spec, account_currency, entry, given_rate)


def _validate_levels(
    direction: Direction, entry: Decimal, stop_loss: Decimal, tps: Sequence[TakeProfit]
) -> None:
    if entry <= 0 or stop_loss <= 0:
        raise RiskInputError("invalid_price", "Prices must be positive")
    sign = 1 if direction == "long" else -1
    if (entry - stop_loss) * sign <= 0:
        raise RiskInputError(
            "stop_loss_wrong_side",
            "Stop loss must be below entry for a long and above it for a short",
        )
    for tp in tps:
        if (tp.price - entry) * sign <= 0:
            raise RiskInputError(
                "take_profit_wrong_side",
                "Take profit must be above entry for a long and below it for a short",
                {"price": str(tp.price)},
            )
    if sum((tp.pct for tp in tps), Decimal(0)) > 100:
        raise RiskInputError("take_profit_pct_over_100", "Take-profit shares exceed 100%")


def round_lot(spec: SymbolSpec, lot: Decimal) -> Decimal:
    """Round down to the lot step (never risk more than asked) and clamp to the broker limits."""
    steps = (lot / spec.lot_step).to_integral_value(rounding=ROUND_DOWN)
    return min(max(steps * spec.lot_step, spec.min_lot), spec.max_lot)


def calculate(inp: CalcInput) -> CalcResult:
    if (inp.risk_pct is None) == (inp.lot is None):
        raise RiskInputError("risk_or_lot", "Give exactly one of risk_pct or lot")
    if inp.balance <= 0:
        raise RiskInputError("invalid_balance", "Balance must be positive")
    _validate_levels(inp.direction, inp.entry, inp.stop_loss, inp.take_profits)

    per_unit = value_per_price_unit(
        inp.spec, inp.account_currency, inp.entry, inp.quote_to_account_rate
    )
    distance = abs(inp.entry - inp.stop_loss)
    risk_per_lot = distance * per_unit

    target: Decimal | None = None
    if inp.risk_pct is not None:
        if not Decimal(0) < inp.risk_pct <= 100:
            raise RiskInputError("invalid_risk_pct", "risk_pct must be in (0, 100]")
        target = inp.balance * inp.risk_pct / 100
        lot = round_lot(inp.spec, target / risk_per_lot)
    else:
        assert inp.lot is not None
        if inp.lot <= 0:
            raise RiskInputError("invalid_lot", "lot must be positive")
        lot = inp.lot

    risk_amount = risk_per_lot * lot
    rrs = [abs(tp.price - inp.entry) / distance for tp in inp.take_profits]
    total_pct = sum((tp.pct for tp in inp.take_profits), Decimal(0))
    rr_avg = (
        sum((r * tp.pct for r, tp in zip(rrs, inp.take_profits, strict=True)), Decimal(0))
        / total_pct
        if total_pct > 0
        else None
    )

    def q(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    return CalcResult(
        lot=lot.quantize(inp.spec.lot_step),
        risk_amount=q(risk_amount),
        risk_pct=q(risk_amount / inp.balance * 100),
        target_risk_amount=q(target) if target is not None else None,
        value_per_point=(per_unit * inp.spec.point_size).quantize(Decimal("0.000001")),
        sl_points=(distance / inp.spec.point_size).quantize(Decimal(1)),
        rr_per_tp=[q(r) for r in rrs],
        rr_avg=q(rr_avg) if rr_avg is not None else None,
    )
