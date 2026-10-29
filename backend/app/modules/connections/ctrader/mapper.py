"""cTrader Open API payloads → the shared ingest batch (`IngestIn`). Pure functions.

cTrader units:
  * volume is in hundredths of a unit ("cents"); lots = volume / symbol.lotSize (also cents),
  * money is an integer scaled by `moneyDigits` (10^-moneyDigits),
  * deal prices are plain doubles; trendbar prices are integers in 1/100 000,
  * times are epoch milliseconds (trendbars: minutes).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.modules.connections.ctrader import protocol as p
from app.modules.connections.schemas import (
    AccountIn,
    DealIn,
    IngestIn,
    ModificationIn,
    OhlcIn,
    OpenPositionIn,
    SymbolIn,
)

LOT_Q = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    symbol_id: int
    name: str
    digits: int
    lot_size: int  # cents of units in one lot (e.g. 10 000 000 for 100 000 units)


def _money(value: int | None, digits: int) -> Decimal:
    return (Decimal(value or 0) / (Decimal(10) ** digits)).quantize(Decimal("0.01"))


def _price(value: float | int | None, digits: int) -> Decimal:
    if not value:
        return Decimal(0)
    return Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def lots(volume: int, symbol: SymbolInfo) -> Decimal:
    return (Decimal(volume) / Decimal(symbol.lot_size)).quantize(LOT_Q, rounding=ROUND_HALF_UP)


def symbol_info(light: Mapping[str, Any], full: Mapping[str, Any]) -> SymbolInfo:
    """`light` from SymbolsListRes (name), `full` from SymbolByIdRes (digits, lotSize)."""
    return SymbolInfo(
        symbol_id=int(full["symbolId"]),
        name=str(light.get("symbolName") or full.get("symbolName") or full["symbolId"]),
        digits=int(full.get("digits", 5)),
        lot_size=int(full.get("lotSize", 10_000_000)),
    )


def deal(raw: Mapping[str, Any], symbols: Mapping[int, SymbolInfo]) -> DealIn | None:
    """A filled deal; None for anything that didn't trade or has an unknown symbol."""
    if int(raw.get("dealStatus", p.DEAL_FILLED)) not in (p.DEAL_FILLED, p.DEAL_PARTIALLY_FILLED):
        return None
    sym = symbols.get(int(raw["symbolId"]))
    if sym is None:
        return None
    money_digits = int(raw.get("moneyDigits", 2))
    side = "buy" if int(raw["tradeSide"]) == p.BUY else "sell"
    close = raw.get("closePositionDetail")
    filled = int(raw.get("filledVolume") or raw.get("volume") or 0)
    common = {
        "ticket": str(raw["dealId"]),
        "order": str(raw.get("orderId", "")),
        "position_id": str(raw["positionId"]),
        "symbol": sym.name,
        "type": side,
        "volume": lots(filled, sym),
        "price": _price(raw.get("executionPrice"), sym.digits),
        "time": int(raw["executionTimestamp"]) // 1000,
        "commission": _money(raw.get("commission"), money_digits),
    }
    if close:
        cd = int(close.get("moneyDigits", money_digits))
        return DealIn(
            **common,
            entry="out",
            swap=_money(close.get("swap"), cd),
            profit=_money(close.get("grossProfit"), cd),
        )
    return DealIn(**common, entry="in")


def position(raw: Mapping[str, Any], symbols: Mapping[int, SymbolInfo]) -> OpenPositionIn | None:
    trade = raw.get("tradeData", {})
    sym = symbols.get(int(trade.get("symbolId", -1)))
    if sym is None:
        return None
    return OpenPositionIn(
        position_id=str(raw["positionId"]),
        symbol=sym.name,
        type="buy" if int(trade.get("tradeSide", p.BUY)) == p.BUY else "sell",
        volume=lots(int(trade.get("volume", 0)), sym),
        price_open=_price(raw.get("price"), sym.digits),
        sl=_price(raw.get("stopLoss"), sym.digits),
        tp=_price(raw.get("takeProfit"), sym.digits),
        time=int(trade["openTimestamp"]) // 1000 if trade.get("openTimestamp") else None,
    )


def modifications(
    before: OpenPositionIn | None, after: OpenPositionIn, at_ms: int
) -> list[ModificationIn]:
    """SL/TP changes between two snapshots of one position (execution event / reconcile)."""
    if before is None:
        return []
    out = []
    for field in ("sl", "tp"):
        old, new = getattr(before, field), getattr(after, field)
        if old != new:
            out.append(
                ModificationIn(
                    id=f"{after.position_id}:{field}:{at_ms}",
                    position_id=after.position_id,
                    field=field,
                    old=old,
                    new=new,
                    time=at_ms // 1000,
                )
            )
    return out


def trendbars(raw: Sequence[Mapping[str, Any]], timeframe: str, symbol: SymbolInfo) -> OhlcIn:
    """Trendbar = low + deltas, integers in 1/100 000; time in minutes."""
    q = Decimal(1).scaleb(-symbol.digits)

    def px(v: int) -> Decimal:
        return (Decimal(v) / p.PRICE_SCALE).quantize(q, rounding=ROUND_HALF_UP)

    bars = []
    for b in raw:
        low = int(b.get("low", 0))
        bars.append(
            (
                int(b["utcTimestampInMinutes"]) * 60,
                px(low + int(b.get("deltaOpen", 0))),
                px(low + int(b.get("deltaHigh", 0))),
                px(low),
                px(low + int(b.get("deltaClose", 0))),
                Decimal(int(b.get("volume", 0))),
            )
        )
    return OhlcIn(symbol=symbol.name, timeframe=timeframe, bars=bars)


def trader_account(raw: Mapping[str, Any], *, login: str, is_live: bool | None) -> AccountIn:
    digits = int(raw.get("moneyDigits", 2))
    balance = _money(raw.get("balance"), digits)
    return AccountIn(
        login=login,
        server=str(raw.get("brokerName", "")),
        currency="",
        balance=balance,
        equity=balance,  # Open API has no equity without a price feed
        is_live=is_live,
    )


def symbol_specs(symbols: Sequence[SymbolInfo]) -> list[SymbolIn]:
    return [SymbolIn(name=s.name, digits=s.digits) for s in symbols]


def batch(
    account: AccountIn,
    *,
    symbols: Sequence[SymbolInfo] = (),
    deals: Sequence[DealIn] = (),
    positions: Sequence[OpenPositionIn] = (),
    mods: Sequence[ModificationIn] = (),
    ohlc: Sequence[OhlcIn] = (),
    history: tuple[int, int, bool] | None = None,
) -> IngestIn:
    data: dict[str, Any] = {
        "ea_version": "ctrader",
        "account": account,
        "symbols": symbol_specs(symbols),
        "deals": list(deals),
        "positions": list(positions),
        "modifications": list(mods),
        "ohlc": list(ohlc),
    }
    if history is not None:
        data["history"] = {"from": history[0], "to": history[1], "final": history[2]}
    return IngestIn.model_validate(data)
