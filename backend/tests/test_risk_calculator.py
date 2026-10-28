"""Risk calculator (F-03 AC3): money at risk matches MT5 within 1%, lot sizing, R:R."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.modules.risk.calculator import (
    CalcInput,
    ConversionRateRequired,
    RiskInputError,
    SymbolSpec,
    TakeProfit,
    calculate,
)

FIXTURE = Path(__file__).parent / "fixtures" / "risk_mt5.csv"
SEEDS = Path(__file__).resolve().parents[1] / "app" / "seeds" / "symbols.yaml"
SPECS = {s["code"]: s for s in yaml.safe_load(SEEDS.read_text(encoding="utf-8"))["symbols"]}


def spec(code: str, **overrides: Any) -> SymbolSpec:
    s = SPECS[code]
    values: dict[str, Any] = {
        "code": code,
        "contract_size": Decimal(s["contract_size"]),
        "point_size": Decimal(s["point_size"]),
        "base_currency": s["base_currency"],
        "quote_currency": s["quote_currency"],
    }
    values.update(overrides)
    return SymbolSpec(**values)


def _golden() -> list[dict[str, str]]:
    text = FIXTURE.read_text(encoding="utf-8").splitlines()
    return list(csv.DictReader(line for line in text if not line.startswith("#")))


@pytest.mark.parametrize("row", _golden(), ids=lambda r: r["case"])
def test_loss_at_sl_matches_mt5_within_1pct(row: dict[str, str]) -> None:
    result = calculate(
        CalcInput(
            spec=spec(row["symbol"]),
            account_currency=row["account_ccy"],
            balance=Decimal("100000"),
            direction=row["direction"],  # type: ignore[arg-type]
            entry=Decimal(row["entry"]),
            stop_loss=Decimal(row["sl"]),
            lot=Decimal(row["lot"]),
            quote_to_account_rate=Decimal(row["quote_rate"]) if row["quote_rate"] else None,
        )
    )
    expected = Decimal(row["expected_loss"])
    assert abs(result.risk_amount - expected) / expected <= Decimal("0.01"), result


@pytest.mark.parametrize(
    ("code", "balance", "risk_pct", "entry", "sl", "lot", "risk"),
    [
        ("EURUSD", "100000", "1", "1.08500", "1.08000", "2.00", "1000.00"),
        ("XAUUSD", "100000", "1", "4387.52", "4377.52", "1.00", "1000.00"),
        # 0.21034 lots rounds DOWN to 0.21 — never more risk than asked.
        ("EURUSD", "10517", "1", "1.08500", "1.08000", "0.21", "105.00"),
        ("USDJPY", "8412", "0.5", "150.000", "149.500", "0.12", "40.00"),
    ],
)
def test_lot_from_risk_pct(
    code: str, balance: str, risk_pct: str, entry: str, sl: str, lot: str, risk: str
) -> None:
    result = calculate(
        CalcInput(
            spec=spec(code),
            account_currency="USD",
            balance=Decimal(balance),
            direction="long",
            entry=Decimal(entry),
            stop_loss=Decimal(sl),
            risk_pct=Decimal(risk_pct),
        )
    )
    assert result.lot == Decimal(lot)
    assert result.risk_amount == Decimal(risk)
    assert result.target_risk_amount is not None
    assert result.risk_amount <= result.target_risk_amount


def test_lot_never_below_broker_minimum() -> None:
    result = calculate(
        CalcInput(
            spec=spec("XAUUSD"),
            account_currency="USD",
            balance=Decimal("500"),
            direction="long",
            entry=Decimal("4387.52"),
            stop_loss=Decimal("4337.52"),
            risk_pct=Decimal("0.5"),
        )
    )
    assert result.lot == Decimal("0.01")
    # Minimum lot risks more than asked; the real % is reported so the UI can warn.
    assert result.risk_amount == Decimal("50.00")
    assert result.risk_pct == Decimal("10.00")


def test_rr_per_tp_and_weighted_average() -> None:
    result = calculate(
        CalcInput(
            spec=spec("EURUSD"),
            account_currency="USD",
            balance=Decimal("100000"),
            direction="short",
            entry=Decimal("1.08500"),
            stop_loss=Decimal("1.09000"),
            take_profits=[
                TakeProfit(Decimal("1.08000"), Decimal("50")),
                TakeProfit(Decimal("1.07000"), Decimal("50")),
            ],
            risk_pct=Decimal("1"),
        )
    )
    assert result.rr_per_tp == [Decimal("1.00"), Decimal("3.00")]
    assert result.rr_avg == Decimal("2.00")
    assert result.sl_points == Decimal("500")
    assert result.value_per_point == Decimal("1.000000")  # $1 per point per lot


def test_broker_tick_value_override_wins() -> None:
    """MT5's SYMBOL_TRADE_TICK_VALUE (per point per lot) replaces the derived value."""
    result = calculate(
        CalcInput(
            spec=spec("GBPJPY", tick_value=Decimal("0.6667")),
            account_currency="USD",
            balance=Decimal("100000"),
            direction="long",
            entry=Decimal("190.000"),
            stop_loss=Decimal("189.500"),
            lot=Decimal("1"),
        )
    )
    assert abs(result.risk_amount - Decimal("333.33")) <= Decimal("0.5")


def test_cross_without_rate_asks_for_it() -> None:
    with pytest.raises(ConversionRateRequired) as exc:
        calculate(
            CalcInput(
                spec=spec("GBPJPY"),
                account_currency="USD",
                balance=Decimal("100000"),
                direction="long",
                entry=Decimal("190"),
                stop_loss=Decimal("189.5"),
                lot=Decimal("1"),
            )
        )
    assert exc.value.details == {"from": "JPY", "to": "USD"}


@pytest.mark.parametrize(
    ("direction", "sl", "tps", "code"),
    [
        ("long", "1.09", [], "stop_loss_wrong_side"),
        ("short", "1.08", [], "stop_loss_wrong_side"),
        ("long", "1.08", ["1.07"], "take_profit_wrong_side"),
        ("long", "1.085", [], "stop_loss_wrong_side"),  # SL == entry
    ],
)
def test_level_validation(direction: str, sl: str, tps: list[str], code: str) -> None:
    with pytest.raises(RiskInputError) as exc:
        calculate(
            CalcInput(
                spec=spec("EURUSD"),
                account_currency="USD",
                balance=Decimal("100000"),
                direction=direction,  # type: ignore[arg-type]
                entry=Decimal("1.085"),
                stop_loss=Decimal(sl),
                take_profits=[TakeProfit(Decimal(p)) for p in tps],
                risk_pct=Decimal("1"),
            )
        )
    assert exc.value.code == code


def test_exactly_one_of_risk_or_lot() -> None:
    base: dict[str, Any] = {
        "spec": spec("EURUSD"),
        "account_currency": "USD",
        "balance": Decimal("1000"),
        "direction": "long",
        "entry": Decimal("1.085"),
        "stop_loss": Decimal("1.08"),
    }
    for extra in ({}, {"risk_pct": Decimal(1), "lot": Decimal(1)}):
        with pytest.raises(RiskInputError) as exc:
            calculate(CalcInput(**base, **extra))
        assert exc.value.code == "risk_or_lot"
