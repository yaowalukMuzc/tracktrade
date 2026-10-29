"""Execution ↔ plan matching rules (F-10). Pure functions — no DB.

A locked plan is a candidate for a position when symbol, account and direction agree (the
caller filters those) and
  * time:  locked_at <= entry time <= valid_until (no valid_until = open ended), and
  * price: |first fill - plan entry| <= tolerance x |plan entry - plan SL|   (default 0.3, S3).
Plan prices are the ones in force at the entry — a revision made after the entry does not
move the target.

Exactly one candidate → auto-match. None or several → `pending`: the trader picks (AC2).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal


@dataclass(frozen=True, slots=True)
class PlanTarget:
    plan_id: uuid.UUID
    entry_price: Decimal
    stop_loss: Decimal
    locked_at: datetime | None
    valid_until: datetime | None


@dataclass(frozen=True, slots=True)
class Evaluation:
    plan_id: uuid.UUID
    distance: Decimal  # |fill - plan entry|
    pct_of_sl: Decimal  # distance / SL distance x 100
    within_price: bool
    within_time: bool

    @property
    def eligible(self) -> bool:
        return self.within_price and self.within_time


@dataclass(frozen=True, slots=True)
class Decision:
    status: Literal["auto", "pending"]
    plan_id: uuid.UUID | None
    recommended: uuid.UUID | None
    evaluations: list[Evaluation]


def evaluate(
    target: PlanTarget, fill_price: Decimal, opened_at: datetime, tolerance: Decimal
) -> Evaluation:
    sl_distance = abs(target.entry_price - target.stop_loss)
    distance = abs(fill_price - target.entry_price)
    pct = (
        (distance / sl_distance * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if sl_distance
        else Decimal(0)
    )
    within_time = (
        target.locked_at is not None
        and target.locked_at <= opened_at
        and (target.valid_until is None or opened_at <= target.valid_until)
    )
    return Evaluation(
        plan_id=target.plan_id,
        distance=distance,
        pct_of_sl=pct,
        within_price=bool(sl_distance) and distance <= tolerance * sl_distance,
        within_time=within_time,
    )


def decide(
    targets: Sequence[PlanTarget], fill_price: Decimal, opened_at: datetime, tolerance: Decimal
) -> Decision:
    evaluations = sorted(
        (evaluate(t, fill_price, opened_at, tolerance) for t in targets),
        key=lambda e: (not e.eligible, e.distance),
    )
    eligible = [e for e in evaluations if e.eligible]
    recommended = eligible[0].plan_id if eligible else None
    if len(eligible) == 1:
        return Decision("auto", eligible[0].plan_id, recommended, evaluations)
    return Decision("pending", None, recommended, evaluations)


def is_unplanned(plan_locked_at: datetime | None, opened_at: datetime) -> bool:
    """F-07 AC3: a plan that was not locked before the entry does not count as a plan."""
    return plan_locked_at is None or plan_locked_at > opened_at
