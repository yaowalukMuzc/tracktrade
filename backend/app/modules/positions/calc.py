"""Position maths from fills (F-07 AC1-AC2). Pure functions — no DB, no I/O.

Fills are replayed in time order the way MT5 books them: an entry moves the average open
price, an exit realises (exit - average open) x lots x value-per-price-unit. So scale-ins and
partial closes in any order give the broker's numbers. When the broker reported the profit of
every exit (synced trades) that figure is used instead, because it already includes the exact
currency conversion of the moment.

Initial risk = what every entry would have lost at the initial stop loss; R = net P/L / initial
risk. Example from the design (screens/mobile/10-ManualTrade.png): SHORT XAUUSD 0.30 @ 4402.10 +
0.20 @ 4404.80, SL 4412.40, exits 0.25 @ 4388.00 / 4379.50, commission -3.50
→ avg 4403.18 / 4383.75, net +968.00, risk 461.00, R +2.10.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

Side = Literal["in", "out"]
Direction = Literal["long", "short"]
# Money (account currency) per 1.0 price move for 1 lot, at a given price.
ValuePerUnit = Callable[[Decimal], Decimal]

CENT = Decimal("0.01")
LOT_STEP = Decimal("0.01")
PRICE_Q = Decimal("0.000001")
ZERO = Decimal(0)


class PositionInputError(ValueError):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details


@dataclass(frozen=True, slots=True)
class Fill:
    side: Side
    lot: Decimal
    price: Decimal
    at: datetime
    commission: Decimal = ZERO  # signed: cost < 0
    swap: Decimal = ZERO
    profit: Decimal | None = None  # broker-booked profit of an exit


@dataclass(frozen=True, slots=True)
class PositionCalc:
    status: Literal["open", "closed"]
    opened_at: datetime
    closed_at: datetime | None
    first_entry: Decimal
    avg_entry: Decimal
    avg_exit: Decimal | None
    total_lot: Decimal
    open_lot: Decimal
    gross_pnl: Decimal
    commission: Decimal
    swap: Decimal
    net_pnl: Decimal
    initial_risk_amount: Decimal | None
    r_multiple: Decimal | None


def _q(value: Decimal, step: Decimal = CENT) -> Decimal:
    return value.quantize(step, rounding=ROUND_HALF_UP)


def ordered(fills: Sequence[Fill]) -> list[Fill]:
    """Time order; at the same instant an entry comes before an exit."""
    return sorted(fills, key=lambda f: (f.at, 0 if f.side == "in" else 1))


def validate(direction: Direction, fills: Sequence[Fill], initial_sl: Decimal | None) -> None:
    if not fills:
        raise PositionInputError("no_executions", "Add at least one entry")
    for i, f in enumerate(fills):
        if f.lot <= 0 or f.price <= 0:
            raise PositionInputError(
                "invalid_execution", "Lot and price must be positive", {"index": i}
            )
    seq = ordered(fills)
    if seq[0].side != "in":
        raise PositionInputError("exit_before_entry", "The first execution must be an entry")
    open_lot = ZERO
    for f in seq:
        open_lot += f.lot if f.side == "in" else -f.lot
        if open_lot < 0:
            raise PositionInputError(
                "exit_exceeds_open", "Exits close more lots than are open", {"at": f.at.isoformat()}
            )
    if initial_sl is not None:
        sign = 1 if direction == "long" else -1
        if (seq[0].price - initial_sl) * sign <= 0:
            raise PositionInputError(
                "stop_loss_wrong_side",
                "Stop loss must be below the entry for a long and above it for a short",
            )


def compute(
    direction: Direction,
    fills: Sequence[Fill],
    value_per_unit: ValuePerUnit,
    *,
    initial_sl: Decimal | None = None,
) -> PositionCalc:
    """Averages, P/L, R. Call `validate` first for user input; synced data is trusted."""
    seq = ordered(fills)
    entries = [f for f in seq if f.side == "in"]
    exits = [f for f in seq if f.side == "out"]
    if not entries:
        raise PositionInputError("no_executions", "A position needs an entry")
    sign = Decimal(1) if direction == "long" else Decimal(-1)

    total_in = sum((f.lot for f in entries), ZERO)
    total_out = sum((f.lot for f in exits), ZERO)
    avg_entry = sum((f.lot * f.price for f in entries), ZERO) / total_in
    avg_exit = sum((f.lot * f.price for f in exits), ZERO) / total_out if exits else None

    # Replay: realised P/L of each exit against the average open price at that moment.
    open_lot, avg_open, replayed = ZERO, ZERO, ZERO
    for f in seq:
        if f.side == "in":
            avg_open = (avg_open * open_lot + f.price * f.lot) / (open_lot + f.lot)
            open_lot += f.lot
        else:
            replayed += sign * (f.price - avg_open) * f.lot * value_per_unit(f.price)
            open_lot -= f.lot
    broker_profit = exits and all(f.profit is not None for f in exits)
    gross = sum((f.profit or ZERO for f in exits), ZERO) if broker_profit else replayed

    commission = sum((f.commission for f in seq), ZERO)
    swap = sum((f.swap for f in seq), ZERO)
    net = gross + commission + swap
    open_lot = max(total_in - total_out, ZERO)
    closed = bool(exits) and open_lot == 0

    risk: Decimal | None = None
    if initial_sl is not None:
        at_risk = sum(
            (
                max(sign * (f.price - initial_sl), ZERO) * f.lot * value_per_unit(f.price)
                for f in entries
            ),
            ZERO,
        )
        risk = _q(at_risk) if at_risk > 0 else None
    # R only for a finished trade: an open one has no net result yet.
    r_multiple = _q(net / risk) if risk and closed else None

    return PositionCalc(
        status="closed" if closed else "open",
        opened_at=seq[0].at,
        closed_at=exits[-1].at if closed else None,
        first_entry=entries[0].price,
        avg_entry=_q(avg_entry, PRICE_Q),
        avg_exit=_q(avg_exit, PRICE_Q) if avg_exit is not None else None,
        total_lot=_q(total_in, LOT_STEP),
        open_lot=_q(open_lot, LOT_STEP),
        gross_pnl=_q(gross),
        commission=_q(commission),
        swap=_q(swap),
        net_pnl=_q(net),
        initial_risk_amount=risk,
        r_multiple=r_multiple,
    )


@dataclass(frozen=True, slots=True)
class Excursion:
    mae: Decimal  # worst move against the position, price distance >= 0
    mfe: Decimal  # best move in favour, price distance >= 0


def excursions(
    direction: Direction, avg_entry: Decimal, highs: Sequence[Decimal], lows: Sequence[Decimal]
) -> Excursion | None:
    """MAE / MFE from the bars covering the time the position was open."""
    if not highs or not lows:
        return None
    hi, lo = max(highs), min(lows)
    if direction == "long":
        mae, mfe = avg_entry - lo, hi - avg_entry
    else:
        mae, mfe = hi - avg_entry, avg_entry - lo
    return Excursion(mae=_q(max(mae, ZERO), PRICE_Q), mfe=_q(max(mfe, ZERO), PRICE_Q))


def risk_direction(
    direction: Direction, field: str, old: Decimal | None, new: Decimal | None
) -> Literal["increase", "decrease", "neutral"]:
    """How an SL/TP change moves the money at risk (adherence + in-trade prompt input).

    SL further from price (or removed) = more risk; closer (or first set) = less. TP changes
    don't change the risk.
    """
    if field != "sl" or old == new:
        return "neutral"
    if new is None:
        return "increase"
    if old is None:
        return "decrease"
    wider = new < old if direction == "long" else new > old
    return "increase" if wider else "decrease"
