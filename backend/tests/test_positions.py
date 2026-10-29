"""Positions API: manual entry (F-07), matching (F-10), list/tabs, ownership, Today, risk status."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from fastapi import FastAPI

from tests.conftest import auth, signup
from tests.test_plans import PLANS, _locked, _plan, _world

POS = "/api/v1/positions"
D = Decimal


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


def _now() -> datetime:
    """Whole second just after now — an entry made right after the plan was locked."""
    return datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=1)


def _body(w: dict[str, Any], **over: Any) -> dict[str, Any]:
    """LONG XAUUSD 0.48 @ 4387.60 (design 06 trade), closed 0.48 @ 4398.38, SL 4367.60."""
    t = over.pop("t", _now())
    body: dict[str, Any] = {
        "account_id": w["account"]["id"],
        "symbol_id": w["symbols"]["XAUUSD"]["id"],
        "direction": "long",
        "initial_sl": "4367.60",
        "initial_tp": "4418",
        "executions": [
            {"side": "in", "lot": "0.48", "price": "4387.60", "executed_at": _iso(t)},
            {
                "side": "out",
                "lot": "0.48",
                "price": "4398.38",
                "executed_at": _iso(t + timedelta(minutes=30)),
                "commission": "-3.36",
            },
        ],
    }
    body.update(over)
    return body


async def _create(client: httpx.AsyncClient, w: dict[str, Any], **over: Any) -> dict[str, Any]:
    res = await client.post(POS, headers=w["h"], json=_body(w, **over))
    assert res.status_code == 201, res.text
    out: dict[str, Any] = res.json()
    return out


async def _plan_status(client: httpx.AsyncClient, w: dict[str, Any], plan_id: str) -> str:
    res = await client.get(f"{PLANS}/{plan_id}", headers=w["h"])
    assert res.status_code == 200, res.text
    status: str = res.json()["status"]
    return status


# ------------------------------------------------------------------ F-07 manual entry


async def test_manual_scale_in_partial_close_design_numbers(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-07 AC1-AC2: screens/mobile/10-ManualTrade.png — SHORT, 2 entries, 2 exits."""
    w = await _world(client, app)
    t = _now() - timedelta(hours=3)
    body = _body(
        w,
        direction="short",
        initial_sl="4412.40",
        initial_tp="4371.00",
        executions=[
            {
                "side": "in",
                "lot": "0.30",
                "price": "4402.10",
                "executed_at": _iso(t),
                "commission": "-2.10",
            },
            {
                "side": "in",
                "lot": "0.20",
                "price": "4404.80",
                "executed_at": _iso(t + timedelta(minutes=21)),
                "commission": "-1.40",
            },
            {
                "side": "out",
                "lot": "0.25",
                "price": "4388.00",
                "executed_at": _iso(t + timedelta(minutes=70)),
            },
            {
                "side": "out",
                "lot": "0.25",
                "price": "4379.50",
                "executed_at": _iso(t + timedelta(minutes=105)),
            },
        ],
    )
    preview = await client.post(f"{POS}/preview", headers=w["h"], json=body)
    assert preview.status_code == 200, preview.text
    calc = preview.json()
    assert (D(calc["avg_entry"]), D(calc["avg_exit"])) == (D("4403.18"), D("4383.75"))
    assert (D(calc["net_pnl"]), D(calc["r_multiple"]), calc["status"]) == (
        D("968.00"),
        D("2.10"),
        "closed",
    )
    # Preview saves nothing.
    assert (await client.get(POS, headers=w["h"])).json()["total"] == 0

    pos = (await client.post(POS, headers=w["h"], json=body)).json()
    assert pos["ref_no"] == 1 and pos["source"] == "manual" and pos["status"] == "closed"
    assert D(pos["total_lot"]) == D("0.50") and D(pos["commission"]) == D("-3.50")
    assert D(pos["initial_risk_amount"]) == D("461.00")
    assert [e["side"] for e in pos["executions"]] == ["in", "in", "out", "out"]
    # No plan exists → nothing to match → waits in the queue, unplanned meanwhile (F-10 AC2).
    assert (pos["match_status"], pos["is_unplanned"], pos["plan"]) == ("pending", True, None)
    assert pos["unplanned_reason"] == "no_plan"
    assert pos["risk_profile_version"] == 1


async def test_ref_no_runs_per_user(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    a, b = await _create(client, w, unplanned=True), await _create(client, w, unplanned=True)
    assert (a["ref_no"], b["ref_no"]) == (1, 2)
    other = await _world(client, app, "other@example.com")
    assert (await _create(client, other, unplanned=True))["ref_no"] == 1


async def test_open_position_has_no_r(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    body = _body(w)
    body["executions"] = body["executions"][:1]
    pos = (await client.post(POS, headers=w["h"], json=body)).json()
    assert (pos["status"], pos["closed_at"], pos["r_multiple"]) == ("open", None, None)
    assert D(pos["open_lot"]) == D("0.48")


async def test_manual_validation(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    t = _now()
    cases: list[tuple[dict[str, Any], str]] = [
        (
            {
                "executions": [
                    {"side": "out", "lot": "0.1", "price": "4380", "executed_at": _iso(t)},
                    {
                        "side": "in",
                        "lot": "0.1",
                        "price": "4380",
                        "executed_at": _iso(t + timedelta(minutes=1)),
                    },
                ]
            },
            "exit_before_entry",
        ),
        (
            {
                "executions": [
                    {"side": "in", "lot": "0.1", "price": "4380", "executed_at": _iso(t)},
                    {
                        "side": "out",
                        "lot": "0.2",
                        "price": "4390",
                        "executed_at": _iso(t + timedelta(minutes=1)),
                    },
                ]
            },
            "exit_exceeds_open",
        ),
        ({"initial_sl": "4400"}, "stop_loss_wrong_side"),
        ({"plan_id": w["setup"]["id"], "unplanned": True}, "validation_error"),
        ({"executions": []}, "validation_error"),
    ]
    for over, code in cases:
        res = await client.post(POS, headers=w["h"], json=_body(w, **over))
        assert res.status_code == 422, (code, res.text)
        assert res.json()["code"] == code


async def test_naive_timestamp_rejected(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    body = _body(w)
    body["executions"][0]["executed_at"] = "2026-10-09T10:05:00"
    res = await client.post(POS, headers=w["h"], json=body)
    assert res.status_code == 422


async def test_cross_pair_needs_rate(client: httpx.AsyncClient, app: FastAPI) -> None:
    """GBPJPY on a USD account can't be valued without the JPY→USD rate."""
    w = await _world(client, app)
    t = _now()
    body = _body(
        w,
        symbol_id=w["symbols"]["GBPJPY"]["id"],
        initial_sl="199.50",
        initial_tp=None,
        executions=[{"side": "in", "lot": "1", "price": "200.10", "executed_at": _iso(t)}],
        unplanned=True,
    )
    res = await client.post(POS, headers=w["h"], json=body)
    assert res.status_code == 422 and res.json()["code"] == "conversion_rate_required"
    body["quote_to_account_rate"] = "0.0066"
    assert (await client.post(POS, headers=w["h"], json=body)).status_code == 201


# ------------------------------------------------------------------ F-10 matching


async def test_single_locked_plan_auto_matches_and_drives_plan_status(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-10 AC1: one locked plan in tolerance → auto; plan triggered → closed with the trade."""
    w = await _world(client, app)
    plan = await _locked(client, w)
    body = _body(w)
    body["executions"] = body["executions"][:1]  # still open
    pos = (await client.post(POS, headers=w["h"], json=body)).json()
    assert (pos["match_status"], pos["is_unplanned"]) == ("auto", False)
    assert pos["plan"]["id"] == plan["id"] and pos["unplanned_reason"] is None
    assert pos["match_meta"]["decision"] == "auto"
    assert pos["match_meta"]["evaluations"][0]["pct_of_sl"] == "0.4"  # 0.08 / 20.74
    assert await _plan_status(client, w, plan["id"]) == "triggered"

    # Closing every trade of the plan closes the plan.
    closed = await _create(client, w)
    assert closed["plan"]["id"] == plan["id"]
    assert await _plan_status(client, w, plan["id"]) == "triggered"  # first one still open
    await client.delete(f"{POS}/{pos['id']}", headers=w["h"])
    assert await _plan_status(client, w, plan["id"]) == "closed"


async def test_out_of_tolerance_goes_to_queue(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    await _locked(client, w)  # entry 4387.52, SL 4366.78 → tolerance 6.22
    body = _body(w)
    body["executions"][0]["price"] = "4395.00"
    pos = (await client.post(POS, headers=w["h"], json=body)).json()
    assert pos["match_status"] == "pending" and pos["plan"] is None


async def test_two_candidates_pending_then_manual_pick_and_unplanned(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-10 AC2-AC3: several plans fit → queue with the closest recommended; the trader picks;
    switching to unplanned puts the plan back to locked."""
    w = await _world(client, app)
    a = await _locked(client, w)
    c = await _locked(client, w, entry_type="market", entry_price="4392.00", stop_loss="4371.05")
    pos = await _create(client, w)
    assert pos["match_status"] == "pending" and pos["plan"] is None

    res = await client.get(f"{POS}/{pos['id']}/match-candidates", headers=w["h"])
    cands = res.json()
    assert [x["plan"]["id"] for x in cands] == [a["id"], c["id"]]
    assert [x["recommended"] for x in cands] == [True, False]
    assert (D(cands[0]["distance"]), cands[1]["pct_of_sl"]) == (D("0.08"), "21.0")
    assert all(x["eligible"] for x in cands)

    queue = (await client.get(f"{POS}/match-queue", headers=w["h"])).json()
    assert [q["position"]["id"] for q in queue] == [pos["id"]]
    assert queue[0]["first_entry"] == "4387.600000"

    picked = await client.put(f"{POS}/{pos['id']}/match", headers=w["h"], json={"plan_id": c["id"]})
    assert picked.status_code == 200, picked.text
    out = picked.json()
    assert (out["match_status"], out["plan"]["id"], out["is_unplanned"]) == (
        "manual",
        c["id"],
        False,
    )
    assert await _plan_status(client, w, c["id"]) == "closed"
    assert await _plan_status(client, w, a["id"]) == "locked"

    res = await client.put(f"{POS}/{pos['id']}/match", headers=w["h"], json={"plan_id": None})
    out = res.json()
    assert (out["plan"], out["is_unplanned"], out["unplanned_reason"]) == (None, True, "no_plan")
    assert await _plan_status(client, w, c["id"]) == "locked"
    assert (await client.get(f"{POS}/match-queue", headers=w["h"])).json() == []


async def test_plan_locked_after_entry_is_unplanned(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-07 AC3: linking a plan that was locked after the entry still counts as unplanned."""
    w = await _world(client, app)
    entry = _now() - timedelta(hours=1)
    pos = await _create(client, w, t=entry)
    plan = await _locked(client, w)  # locked now, an hour after the entry
    res = await client.put(f"{POS}/{pos['id']}/match", headers=w["h"], json={"plan_id": plan["id"]})
    out = res.json()
    assert (out["plan"]["id"], out["is_unplanned"]) == (plan["id"], True)
    assert out["unplanned_reason"] == "locked_after_entry"
    assert await _plan_status(client, w, plan["id"]) == "locked"  # not triggered by it


async def test_draft_plan_in_form_is_unplanned(client: httpx.AsyncClient, app: FastAPI) -> None:
    """The form lets you pick a draft (design 10) but warns: plan_not_locked."""
    w = await _world(client, app)
    draft = await _plan(client, w)
    opts = await client.get(
        f"{POS}/plan-options",
        headers=w["h"],
        params={
            "account_id": w["account"]["id"],
            "symbol_id": w["symbols"]["XAUUSD"]["id"],
            "direction": "long",
            "opened_at": _iso(_now()),
            "entry_price": "4387.60",
        },
    )
    assert opts.status_code == 200, opts.text
    assert [(o["plan"]["id"], o["plan"]["status"], o["eligible"]) for o in opts.json()] == [
        (draft["id"], "draft", False)
    ]
    body = _body(w, plan_id=draft["id"])
    assert (await client.post(f"{POS}/preview", headers=w["h"], json=body)).json()[
        "unplanned_reason"
    ] == "plan_not_locked"
    pos = (await client.post(POS, headers=w["h"], json=body)).json()
    assert (pos["is_unplanned"], pos["unplanned_reason"], pos["match_status"]) == (
        True,
        "plan_not_locked",
        "manual",
    )
    assert await _plan_status(client, w, draft["id"]) == "draft"


async def test_plan_mismatch(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    short_plan = await _locked(
        client,
        w,
        direction="short",
        entry_price="4387.52",
        stop_loss="4400",
        take_profits=[{"price": "4370", "pct": "100"}],
    )
    res = await client.post(POS, headers=w["h"], json=_body(w, plan_id=short_plan["id"]))
    assert res.status_code == 422 and res.json()["code"] == "plan_mismatch"


async def test_revision_after_entry_does_not_move_match_target(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """Matching compares with the plan as it was at the entry (revision in force then)."""
    w = await _world(client, app)
    plan = await _locked(client, w)
    entry = datetime.now(UTC)  # after the lock, before the revision below
    res = await client.post(
        f"{PLANS}/{plan['id']}/revisions",
        headers=w["h"],
        json={"changes": {"entry_price": "4300", "stop_loss": "4280"}, "reason": "re-plan"},
    )
    assert res.status_code == 201, res.text
    # Recorded later, but the fill happened at `entry`: the lock-time entry 4387.52 applies.
    pos = await _create(client, w, t=entry)
    assert pos["match_status"] == "auto" and pos["plan"]["id"] == plan["id"]
    # A trade entered after the revision is compared with the new entry (4300) → no match.
    later = await _create(client, w, t=_now())
    assert later["match_status"] == "pending"


# ------------------------------------------------------------------ list / tabs / filters


async def test_list_tabs_counts_filters_and_paging(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    base = _now() - timedelta(days=2)
    await _create(client, w, t=base, unplanned=True)  # closed, unplanned
    await _create(client, w, t=base + timedelta(hours=1))  # closed, pending (no plan)
    open_body = _body(w, t=base + timedelta(hours=2), unplanned=True)
    open_body["executions"] = open_body["executions"][:1]
    assert (await client.post(POS, headers=w["h"], json=open_body)).status_code == 201
    eur = _body(
        w,
        t=base + timedelta(hours=3),
        symbol_id=w["symbols"]["EURUSD"]["id"],
        direction="short",
        initial_sl="1.0900",
        initial_tp="1.0800",
        unplanned=True,
        executions=[
            {
                "side": "in",
                "lot": "1",
                "price": "1.0850",
                "executed_at": _iso(base + timedelta(hours=3)),
            },
            {
                "side": "out",
                "lot": "1",
                "price": "1.0860",
                "executed_at": _iso(base + timedelta(hours=4)),
            },
        ],
    )
    assert (await client.post(POS, headers=w["h"], json=eur)).status_code == 201

    res = (await client.get(POS, headers=w["h"])).json()
    assert res["counts"] == {"all": 4, "review": 3, "pending": 1, "unplanned": 3, "open": 1}
    assert [i["symbol_code"] for i in res["items"]] == ["EURUSD", "XAUUSD", "XAUUSD", "XAUUSD"]
    eur_row = res["items"][0]
    assert (eur_row["direction"], D(eur_row["net_pnl"])) == ("short", D("-100.00"))
    assert eur_row["review_status"] == "pending"

    for tab, n in [("pending", 1), ("open", 1), ("unplanned", 3), ("review", 3)]:
        page = (await client.get(POS, headers=w["h"], params={"tab": tab})).json()
        assert (page["total"], len(page["items"])) == (n, n), tab

    page = (await client.get(POS, headers=w["h"], params={"limit": 2, "offset": 2})).json()
    assert (page["total"], len(page["items"]), page["offset"]) == (4, 2, 2)

    sym = (await client.get(POS, headers=w["h"], params={"q": "eur"})).json()
    assert sym["counts"]["all"] == 1
    ref = (await client.get(POS, headers=w["h"], params={"q": "#T-2"})).json()
    assert [i["ref_no"] for i in ref["items"]] == [2]
    by_symbol = (
        await client.get(POS, headers=w["h"], params={"symbol_id": w["symbols"]["EURUSD"]["id"]})
    ).json()
    assert by_symbol["total"] == 1
    future = (_now() + timedelta(days=2)).date().isoformat()
    assert (await client.get(POS, headers=w["h"], params={"from": future})).json()["total"] == 0

    csv = await client.get(f"{POS}/export.csv", headers=w["h"], params={"tab": "review"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.lstrip("﻿").strip().splitlines()
    assert lines[0].startswith("ref_no,account,symbol") and len(lines) == 4


async def test_setup_filter(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    plan = await _locked(client, w)
    await _create(client, w, plan_id=plan["id"])
    await _create(client, w, unplanned=True)
    res = (await client.get(POS, headers=w["h"], params={"setup_id": w["setup"]["id"]})).json()
    assert res["total"] == 1 and res["items"][0]["plan"]["setup_name"] == "London Breakout"


# ------------------------------------------------------------------ ownership (F-01 AC4)


async def test_other_users_positions_are_404(client: httpx.AsyncClient, app: FastAPI) -> None:
    a = await _world(client, app)
    pos = await _create(client, a, unplanned=True)
    plan = await _locked(client, a)
    hb = auth((await signup(app, "b@example.com"))["access_token"])
    for method, path, body in [
        ("GET", f"{POS}/{pos['id']}", None),
        ("GET", f"{POS}/{pos['id']}/match-candidates", None),
        ("PUT", f"{POS}/{pos['id']}/match", {"plan_id": None}),
        ("DELETE", f"{POS}/{pos['id']}", None),
    ]:
        res = await client.request(method, path, headers=hb, json=body)
        assert res.status_code == 404, (method, path, res.text)
    assert (await client.get(POS, headers=hb)).json()["total"] == 0
    # B can't create on A's account or link A's plan.
    res = await client.post(POS, headers=hb, json=_body(a))
    assert res.status_code == 404
    b = await _world(client, app, "b2@example.com")
    res = await client.put(
        f"{POS}/{(await _create(client, b, unplanned=True))['id']}/match",
        headers=b["h"],
        json={"plan_id": plan["id"]},
    )
    assert res.status_code == 404


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    for path in (POS, f"{POS}/match-queue", f"{POS}/export.csv"):
        assert (await client.get(path)).status_code == 401


# ------------------------------------------------------------------ Today + risk status


async def test_today_and_risk_status_use_trades(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    t = _now() - timedelta(minutes=40)
    await _create(client, w, t=t)  # pending, +517.44 - 3.36, closed at t+30
    loss = _body(w, t=t + timedelta(minutes=5), unplanned=True)  # closed at t+35
    loss["executions"][1]["price"] = "4377.60"  # -10 x 0.48 x 100 = -480, -3.36 commission
    assert (await client.post(POS, headers=w["h"], json=loss)).status_code == 201

    today = (await client.get("/api/v1/today", headers=w["h"])).json()
    assert today["todo"]["pending_match"] == 1
    assert today["todo"]["pending_review"] == 2
    # R: -483.36 / 960 = -0.50, +514.08 / 960 = +0.54
    assert today["pnl"] == [{"currency": "USD", "amount": "30.72", "r": "0.04", "trades": 2}]

    acc_id = w["account"]["id"]
    st = (await client.get(f"/api/v1/accounts/{acc_id}/risk-status", headers=w["h"])).json()
    assert D(st["balance"]) == D("100030.72")
    assert D(st["trades_today"]["used"]) == 2
    assert D(st["daily_loss"]["used"]) == 0  # the day is net positive
    # Peak 100 514.08 after the win, then -483.36 → 0.48 % below the peak.
    assert D(st["drawdown_pct"]["used"]) == D("0.48")
