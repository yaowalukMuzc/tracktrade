"""Canonical plan snapshot + sha256 (F-06 AC4).

The hash must not depend on how numbers were typed ("4387.520" == "4387.52"), on key
order or on the database round trip, so every value is normalised first:
decimals → plain strings without trailing zeros, datetimes → UTC ISO seconds, ids → str,
dict keys sorted, the checklist in setup order.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.modules.plans.models import TradePlan

SNAPSHOT_VERSION = 1
# Plan columns a revision may change (the checklist is frozen at lock time).
REVISABLE = (
    "entry_type",
    "entry_price",
    "stop_loss",
    "take_profits",
    "planned_risk_pct",
    "management_plan",
    "invalidation",
    "valid_until",
)


def dec(value: Decimal | str | int | float | None) -> str | None:
    if value is None:
        return None
    text = format(Decimal(str(value)).normalize(), "f")
    return "0" if text in ("-0", "") else text


def ts(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="seconds")


def norm_tps(tps: list[dict[str, Any]]) -> list[dict[str, str | None]]:
    return [{"price": dec(tp["price"]), "pct": dec(tp.get("pct", 100))} for tp in tps]


def norm_management(value: dict[str, Any] | None) -> dict[str, bool]:
    value = value or {}
    return {k: bool(value.get(k, False)) for k in ("partial", "break_even", "trailing")}


def norm_field(name: str, value: Any) -> Any:
    """Comparable, JSON-safe form of one revisable field."""
    if name in ("entry_price", "stop_loss", "planned_risk_pct"):
        return dec(value)
    if name == "take_profits":
        return norm_tps(value)
    if name == "management_plan":
        return norm_management(value)
    if name == "valid_until":
        return ts(value)
    return value


def build(plan: TradePlan, checklist: list[dict[str, Any]]) -> dict[str, Any]:
    """`checklist`: [{"item_id", "text", "is_required", "checked"}] in setup order."""
    return {
        "v": SNAPSHOT_VERSION,
        "analysis_id": str(plan.analysis_id) if plan.analysis_id else None,
        "setup_id": str(plan.setup_id),
        "account_id": str(plan.account_id),
        "symbol_id": str(plan.symbol_id),
        "direction": plan.direction,
        "scenario_label": plan.scenario_label,
        "entry_type": plan.entry_type,
        "entry_price": dec(plan.entry_price),
        "stop_loss": dec(plan.stop_loss),
        "take_profits": norm_tps(plan.take_profits),
        "planned_risk_pct": dec(plan.planned_risk_pct),
        "planned_risk_amount": dec(plan.planned_risk_amount),
        "planned_lot": dec(plan.planned_lot),
        "planned_rr": dec(plan.planned_rr),
        "quote_to_account_rate": dec(plan.quote_to_account_rate),
        "management_plan": norm_management(plan.management_plan),
        "invalidation": plan.invalidation,
        "valid_until": ts(plan.valid_until),
        "checklist": [
            {
                "item_id": str(c["item_id"]),
                "text": c["text"],
                "is_required": bool(c["is_required"]),
                "checked": bool(c["checked"]),
            }
            for c in checklist
        ],
    }


def canonical(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(canonical(snapshot).encode("utf-8")).hexdigest()
