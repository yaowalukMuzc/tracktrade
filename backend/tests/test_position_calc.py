"""Position maths + matching rules (F-07 AC1-AC2, F-10 AC1-AC2) — pure functions, no DB."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.positions.calc import (
    Fill,
    PositionInputError,
    compute,
    excursions,
    risk_direction,
    validate,
)
from app.modules.positions.matching import PlanTarget, decide, evaluate, is_unplanned

D = Decimal
T0 = datetime(2026, 10, 9, 6, 20, tzinfo=UTC)  # 13:20 Bangkok


def gold(_: Decimal) -> Decimal:
    """XAUUSD on a USD account: contract 100 → $100 per 1.0 move per lot."""
    return D(100)


def fill(side: str, lot: str, price: str, minutes: int, **kw: object) -> Fill:
    return Fill(side, D(lot), D(price), T0 + timedelta(minutes=minutes), **kw)  # type: ignore[arg-type]


DESIGN_SHORT = [  # screens/mobile/10-ManualTrade.png
    fill("in", "0.30", "4402.10", 0, commission=D("-2.10")),
    fill("in", "0.20", "4404.80", 21, commission=D("-1.40")),
    fill("out", "0.25", "4388.00", 70),
    fill("out", "0.25", "4379.50", 105),
]


def test_design_example_scale_in_and_partial_close() -> None:
    calc = compute("short", DESIGN_SHORT, gold, initial_sl=D("4412.40"))
    assert calc.avg_entry == D("4403.18")
    assert calc.avg_exit == D("4383.75")
    assert calc.total_lot == D("0.50") and calc.open_lot == D("0.00")
    assert calc.commission == D("-3.50")
    assert calc.gross_pnl == D("971.50")
    assert calc.net_pnl == D("968.00")
    assert calc.initial_risk_amount == D("461.00")  # 0.3x10.30x100 + 0.2x7.60x100
    assert calc.r_multiple == D("2.10")
    assert calc.status == "closed"
    assert calc.opened_at == T0 and calc.closed_at == T0 + timedelta(minutes=105)


def test_open_position_has_no_exit_and_no_r() -> None:
    calc = compute("long", [fill("in", "0.48", "4387.60", 0)], gold, initial_sl=D("4367.60"))
    assert calc.status == "open" and calc.closed_at is None and calc.avg_exit is None
    assert calc.open_lot == D("0.48")
    assert calc.initial_risk_amount == D("960.00")
    assert calc.r_multiple is None
    assert calc.net_pnl == D("0.00")


def test_partial_close_before_scale_in_uses_running_average() -> None:
    # in 1.0 @100, out 0.5 @110 (+0.5x10), in 0.5 @120 → 1.0 open at avg 110, out 1.0 @118 (+1x8)
    fills = [
        fill("in", "1", "100", 0),
        fill("out", "0.5", "110", 1),
        fill("in", "0.5", "120", 2),
        fill("out", "1", "118", 3),
    ]
    calc = compute("long", fills, lambda _: D(1))
    assert calc.gross_pnl == D("13.00")
    # Reported averages weight every entry / exit by lot: (1x100 + 0.5x120) / 1.5.
    assert calc.avg_entry == D("106.666667")
    assert calc.avg_exit == D("115.333333")  # (0.5x110 + 1x118) / 1.5
    assert calc.total_lot == D("1.50") and calc.status == "closed"


def test_broker_profit_wins_over_own_maths() -> None:
    fills = [fill("in", "1", "1.0840", 0), fill("out", "1", "1.0850", 5, profit=D("99.80"))]
    calc = compute("long", fills, lambda _: D(100000))
    assert calc.gross_pnl == D("99.80")


def test_quote_conversion_uses_exit_price_for_pnl() -> None:
    # USDJPY on USD: value per unit = contract / price.
    def usdjpy(price: Decimal) -> Decimal:
        return D(100000) / price

    calc = compute(
        "long",
        [fill("in", "1", "150.00", 0), fill("out", "1", "151.00", 5)],
        usdjpy,
        initial_sl=D("149.50"),
    )
    assert calc.gross_pnl == (D(100000) / D(151)).quantize(D("0.01"))  # 662.25
    assert calc.initial_risk_amount == (D("0.5") * D(100000) / D(150)).quantize(D("0.01"))


def test_swap_and_commission_in_net() -> None:
    fills = [
        fill("in", "1", "100", 0, commission=D("-3")),
        fill("out", "1", "101", 5, commission=D("-3"), swap=D("-1.25")),
    ]
    calc = compute("long", fills, lambda _: D(10))
    assert (calc.gross_pnl, calc.commission, calc.swap, calc.net_pnl) == (
        D("10.00"),
        D("-6.00"),
        D("-1.25"),
        D("2.75"),
    )


@pytest.mark.parametrize(
    ("fills", "sl", "code"),
    [
        ([], None, "no_executions"),
        ([fill("out", "1", "100", 0), fill("in", "1", "99", 1)], None, "exit_before_entry"),
        ([fill("in", "1", "100", 0), fill("out", "2", "101", 1)], None, "exit_exceeds_open"),
        ([fill("in", "0", "100", 0)], None, "invalid_execution"),
        ([fill("in", "1", "100", 0)], D("101"), "stop_loss_wrong_side"),
    ],
)
def test_validation_errors(fills: list[Fill], sl: Decimal | None, code: str) -> None:
    with pytest.raises(PositionInputError) as exc:
        validate("long", fills, sl)
    assert exc.value.code == code


def test_same_minute_entry_sorts_before_exit() -> None:
    fills = [fill("out", "1", "101", 0), fill("in", "1", "100", 0)]
    validate("long", fills, None)  # no "exit before entry"
    assert compute("long", fills, lambda _: D(1)).status == "closed"


def test_excursions_long_and_short() -> None:
    highs, lows = [D("4392"), D("4395.5")], [D("4380.2"), D("4386")]
    long_ = excursions("long", D("4387.60"), highs, lows)
    assert long_ is not None and (long_.mae, long_.mfe) == (D("7.400000"), D("7.900000"))
    short = excursions("short", D("4387.60"), highs, lows)
    assert short is not None and (short.mae, short.mfe) == (D("7.900000"), D("7.400000"))
    assert excursions("long", D(1), [], []) is None


@pytest.mark.parametrize(
    ("direction", "field", "old", "new", "expected"),
    [
        ("long", "sl", "4380", "4375", "increase"),  # widened
        ("long", "sl", "4380", "4387.6", "decrease"),  # to break-even
        ("short", "sl", "4412.4", "4420", "increase"),
        ("short", "sl", "4412.4", "4400", "decrease"),
        ("long", "sl", None, "4380", "decrease"),  # SL added
        ("long", "sl", "4380", None, "increase"),  # SL removed
        ("long", "tp", "4400", "4390", "neutral"),
    ],
)
def test_risk_direction(
    direction: str, field: str, old: str | None, new: str | None, expected: str
) -> None:
    to_d = lambda v: D(v) if v is not None else None  # noqa: E731
    assert risk_direction(direction, field, to_d(old), to_d(new)) == expected  # type: ignore[arg-type]


# ------------------------------------------------------------------ matching

FILL_AT = datetime(2026, 10, 9, 3, 5, tzinfo=UTC)  # 10:05 Bangkok


def target(entry: str, sl: str, locked_min: int = -53, valid_h: int | None = 10) -> PlanTarget:
    return PlanTarget(
        plan_id=uuid.uuid4(),
        entry_price=D(entry),
        stop_loss=D(sl),
        locked_at=FILL_AT + timedelta(minutes=locked_min),
        valid_until=FILL_AT + timedelta(hours=valid_h) if valid_h is not None else None,
    )


def test_design_distances() -> None:
    # Plan A buy limit 4387.52 (SL 20 away) vs fill 4387.60 → 0.08 = 0.4% of the SL distance.
    a = evaluate(target("4387.52", "4367.52"), D("4387.60"), FILL_AT, D("0.3"))
    assert (a.distance, a.pct_of_sl, a.eligible) == (D("0.08"), D("0.4"), True)
    # Plan C market 4392.00 (SL 21 away) → 4.40 = 21% → still within 30%.
    c = evaluate(target("4392.00", "4371.05"), D("4387.60"), FILL_AT, D("0.3"))
    assert (c.distance, c.pct_of_sl, c.within_price) == (D("4.40"), D("21.0"), True)


def test_single_candidate_auto_matches() -> None:
    a = target("4387.52", "4367.52")
    decision = decide([a], D("4387.60"), FILL_AT, D("0.3"))
    assert (decision.status, decision.plan_id, decision.recommended) == (
        "auto",
        a.plan_id,
        a.plan_id,
    )


def test_several_candidates_pending_with_closest_recommended() -> None:
    a, c = target("4387.52", "4367.52"), target("4392.00", "4371.05")
    decision = decide([c, a], D("4387.60"), FILL_AT, D("0.3"))
    assert decision.status == "pending" and decision.plan_id is None
    assert decision.recommended == a.plan_id
    assert [e.plan_id for e in decision.evaluations] == [a.plan_id, c.plan_id]


def test_no_candidate_is_pending() -> None:
    far = target("4300", "4290")  # 87.6 away, SL 10
    decision = decide([far], D("4387.60"), FILL_AT, D("0.3"))
    assert (decision.status, decision.recommended) == ("pending", None)


def test_tolerance_boundary_inclusive() -> None:
    edge = target("100", "90")  # SL distance 10 → tolerance 3.0
    assert evaluate(edge, D("103"), FILL_AT, D("0.3")).within_price
    assert not evaluate(edge, D("103.01"), FILL_AT, D("0.3")).within_price


def test_time_window() -> None:
    locked_after = target("100", "90", locked_min=+5)
    expired = target("100", "90", valid_h=-1)
    open_ended = target("100", "90", valid_h=None)
    assert not evaluate(locked_after, D(100), FILL_AT, D("0.3")).within_time
    assert not evaluate(expired, D(100), FILL_AT, D("0.3")).within_time
    assert evaluate(open_ended, D(100), FILL_AT, D("0.3")).within_time
    draft = PlanTarget(uuid.uuid4(), D(100), D(90), None, None)
    assert not evaluate(draft, D(100), FILL_AT, D("0.3")).within_time


def test_unplanned_rule() -> None:
    assert is_unplanned(None, FILL_AT)
    assert is_unplanned(FILL_AT + timedelta(seconds=1), FILL_AT)
    assert not is_unplanned(FILL_AT - timedelta(minutes=1), FILL_AT)
