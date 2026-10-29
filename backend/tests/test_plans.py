"""Trade plans (F-06 AC1-AC7, F-05 AC3, F-11 AC1): calc, checklist lock, hash, revisions, states."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.modules.plans import service as plans_service
from app.modules.plans import snapshot as snap
from app.modules.plans.models import TradePlan
from app.worker import jobs
from tests.conftest import auth, signup

PLANS = "/api/v1/plans"


async def _world(
    client: httpx.AsyncClient, app: FastAPI, email: str = "nook@example.com"
) -> dict[str, Any]:
    """User + FTMO 100K (USD) + London Breakout setup (2 of 3 items required) + XAUUSD analysis."""
    h = auth((await signup(app, email))["access_token"])
    acc = (
        await client.post(
            "/api/v1/accounts",
            headers=h,
            json={
                "name": "FTMO 100K",
                "broker": "FTMO",
                "platform": "mt5",
                "account_type": "prop",
                "currency": "USD",
                "initial_balance": "100000",
            },
        )
    ).json()
    setup = (
        await client.post(
            "/api/v1/setups",
            headers=h,
            json={
                "name": "London Breakout",
                "timeframes": ["M15", "H1"],
                "sessions": ["london"],
                "default_risk_pct": "1",
                "management_rules": {"partial": {"pct": "50", "at_r": "1.5"}},
                "checklist": [
                    {"text": "H4 bias ตรงทิศทาง", "is_required": True},
                    {"text": "ราคาอยู่ใน demand zone"},
                    {"text": "มีแท่ง confirm บน M15", "is_required": True},
                ],
            },
        )
    ).json()
    symbols = {s["code"]: s for s in (await client.get("/api/v1/symbols", headers=h)).json()}
    analysis = (
        await client.post(
            "/api/v1/analyses",
            headers=h,
            json={
                "account_id": acc["id"],
                "symbol_id": symbols["XAUUSD"]["id"],
                "htf_bias": "bull",
                "timeframes": ["H4", "M15"],
                "session": "london",
                "confidence": 7,
                "key_levels": [{"price": "4366", "kind": "support", "label": "H4 swing low"}],
            },
        )
    ).json()
    return {"h": h, "account": acc, "setup": setup, "symbols": symbols, "analysis": analysis}


def _plan_body(w: dict[str, Any], **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "analysis_id": w["analysis"]["id"],
        "setup_id": w["setup"]["id"],
        "account_id": w["account"]["id"],
        "symbol_id": w["symbols"]["XAUUSD"]["id"],
        "direction": "long",
        "entry_type": "limit",
        "entry_price": "4387.52",
        "stop_loss": "4366.78",
        "take_profits": [{"price": "4418", "pct": "50"}, {"price": "4437.51", "pct": "50"}],
        "planned_risk_pct": "1",
        "management_plan": {"partial": True, "break_even": True},
        "invalidation": "ปิด H1 ต่ำกว่า 4,366",
    }
    body.update(over)
    return body


async def _plan(client: httpx.AsyncClient, w: dict[str, Any], **over: Any) -> dict[str, Any]:
    res = await client.post(PLANS, headers=w["h"], json=_plan_body(w, **over))
    assert res.status_code == 201, res.text
    out: dict[str, Any] = res.json()
    return out


def _tick_all(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"checklist_item_id": i["id"], "checked": True} for i in plan["checklist_items"]]


async def _locked(client: httpx.AsyncClient, w: dict[str, Any], **over: Any) -> dict[str, Any]:
    plan = await _plan(client, w, **over)
    res = await client.patch(
        f"{PLANS}/{plan['id']}", headers=w["h"], json={"checklist_answers": _tick_all(plan)}
    )
    assert res.status_code == 200, res.text
    res = await client.post(f"{PLANS}/{plan['id']}/lock", headers=w["h"])
    assert res.status_code == 200, res.text
    out: dict[str, Any] = res.json()
    return out


async def _trigger(app: FastAPI, plan_id: str) -> None:
    """Phase 4 matching links a position; here we call the same service hook."""
    async with app.state.sessionmaker() as db, db.begin():
        plan = await db.get(TradePlan, uuid.UUID(plan_id))
        assert plan is not None
        await plans_service.mark_triggered(db, plan, datetime.now(UTC))


# ------------------------------------------------------------------ AC1 / AC2


@pytest.mark.parametrize(
    "missing",
    ["setup_id", "direction", "entry_price", "stop_loss", "take_profits", "planned_risk_pct"],
)
async def test_required_fields(client: httpx.AsyncClient, app: FastAPI, missing: str) -> None:
    """F-06 AC1: setup, direction, entry, SL, at least one TP and risk % are required."""
    w = await _world(client, app)
    body = _plan_body(w)
    body.pop(missing)
    res = await client.post(PLANS, headers=w["h"], json=body)
    assert res.status_code == 422, missing
    no_tp = await client.post(PLANS, headers=w["h"], json=_plan_body(w, take_profits=[]))
    assert no_tp.status_code == 422


async def test_planned_lot_risk_and_rr_are_calculated(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-06 AC2: 1% of $100,000 over a 20.74 gold SL → 0.48 lot (rounded down), $995.52."""
    w = await _world(client, app)
    plan = await _plan(client, w)
    assert plan["status"] == "draft"
    assert Decimal(plan["planned_lot"]) == Decimal("0.48")
    assert Decimal(plan["planned_risk_amount"]) == Decimal("995.52")
    assert [Decimal(tp["rr"]) for tp in plan["take_profits"]] == [Decimal("1.47"), Decimal("2.41")]
    assert Decimal(plan["planned_rr"]) == Decimal("1.94")
    assert plan["calc"]["balance"] == "100000.00" and plan["currency"] == "USD"
    assert plan["management_plan"] == {"partial": True, "break_even": True, "trailing": False}

    # Wrong-side levels are rejected by the calculator.
    bad = await client.post(PLANS, headers=w["h"], json=_plan_body(w, stop_loss="4400"))
    assert bad.status_code == 422 and bad.json()["code"] == "stop_loss_wrong_side"

    # Editing a draft recalculates.
    res = await client.patch(
        f"{PLANS}/{plan['id']}", headers=w["h"], json={"planned_risk_pct": "0.5"}
    )
    assert res.status_code == 200
    assert Decimal(res.json()["planned_lot"]) == Decimal("0.24")


async def test_one_analysis_many_scenarios(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-05 AC3: plans A, B, … from one analysis."""
    w = await _world(client, app)
    a = await _plan(client, w)
    b = await _plan(
        client,
        w,
        direction="short",
        entry_type="stop",
        entry_price="4362",
        stop_loss="4378.40",
        take_profits=[{"price": "4322"}],
    )
    assert (a["scenario_label"], b["scenario_label"]) == ("A", "B")
    detail = (await client.get(f"/api/v1/analyses/{w['analysis']['id']}", headers=w["h"])).json()
    assert [p["scenario_label"] for p in detail["plans"]] == ["A", "B"]
    assert detail["plan_count"] == 2
    # The plan's symbol must be the analysis' symbol.
    eur = await client.post(
        PLANS, headers=w["h"], json=_plan_body(w, symbol_id=w["symbols"]["EURUSD"]["id"])
    )
    assert eur.status_code == 422 and eur.json()["code"] == "symbol_mismatch"


# ------------------------------------------------------------------ AC3 / AC4 lock


async def test_lock_needs_required_checklist(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-06 AC3: required items unticked → 422 with the missing items."""
    w = await _world(client, app)
    plan = await _plan(client, w)
    assert plan["can_lock"] is False
    assert plan["checklist"] == {
        "done": 0,
        "total": 3,
        "required_done": 0,
        "required_total": 2,
        "missing": [plan["checklist_items"][0]["id"], plan["checklist_items"][2]["id"]],
    }
    res = await client.post(f"{PLANS}/{plan['id']}/lock", headers=w["h"])
    assert res.status_code == 422
    assert res.json()["code"] == "checklist_incomplete"
    assert [m["text"] for m in res.json()["details"]["missing"]] == [
        "H4 bias ตรงทิศทาง",
        "มีแท่ง confirm บน M15",
    ]
    # Only the optional item ticked: still blocked. Required ones ticked: locks.
    items = plan["checklist_items"]
    answers = [{"checklist_item_id": items[1]["id"], "checked": True}]
    await client.patch(f"{PLANS}/{plan['id']}", headers=w["h"], json={"checklist_answers": answers})
    assert (await client.post(f"{PLANS}/{plan['id']}/lock", headers=w["h"])).status_code == 422
    answers = [
        {"checklist_item_id": items[0]["id"], "checked": True},
        {"checklist_item_id": items[2]["id"], "checked": True, "note": "pin bar"},
    ]
    res = await client.patch(
        f"{PLANS}/{plan['id']}", headers=w["h"], json={"checklist_answers": answers}
    )
    assert res.json()["can_lock"] is True
    locked = await client.post(f"{PLANS}/{plan['id']}/lock", headers=w["h"])
    assert locked.status_code == 200, locked.text
    body = locked.json()
    assert body["status"] == "locked" and body["locked_at"]
    assert len(body["lock_hash"]) == 64 and body["current_revision"] == 1
    assert body["revisions"][0]["snapshot_hash"] == body["lock_hash"]
    assert body["revisions"][0]["reason"] is None


async def test_lock_hash_is_stable(client: httpx.AsyncClient, app: FastAPI) -> None:
    """Same plan typed differently ("4387.520" vs "4387.52") → same hash; DB round trip too."""
    w = await _world(client, app)
    valid = (datetime.now(UTC) + timedelta(hours=6)).replace(microsecond=0)
    one = await _locked(client, w, scenario_label="A", valid_until=valid.isoformat())
    two = await _locked(
        client,
        w,
        scenario_label="A",
        entry_price="4387.520",
        stop_loss="4366.7800",
        take_profits=[{"price": "4418.0", "pct": "50.00"}, {"price": "4437.51", "pct": "50"}],
        planned_risk_pct="1.00",
        valid_until=valid.astimezone().isoformat(),  # same instant, other offset
    )
    assert one["lock_hash"] == two["lock_hash"]

    async with app.state.sessionmaker() as db:
        plan = await db.get(TradePlan, uuid.UUID(one["id"]))
        assert plan is not None
        rev1 = (await plans_service._revisions(db, plan.id))[0]
        assert snap.digest(rev1.snapshot) == one["lock_hash"]
        assert snap.build(plan, rev1.snapshot["checklist"]) == rev1.snapshot
    again = (await client.get(f"{PLANS}/{one['id']}", headers=w["h"])).json()
    assert again["lock_hash"] == one["lock_hash"]


async def test_locked_plan_changes_only_through_revisions(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-06 AC4: no PATCH after lock; a revision always has a reason; revisions are append-only."""
    w = await _world(client, app)
    plan = await _locked(client, w)
    pid = plan["id"]
    patch = await client.patch(f"{PLANS}/{pid}", headers=w["h"], json={"stop_loss": "4360"})
    assert patch.status_code == 409 and patch.json()["code"] == "plan_not_draft"

    change = {"stop_loss": "4360"}
    for reason in (None, "", "   "):
        body: dict[str, Any] = {"changes": change}
        if reason is not None:
            body["reason"] = reason
        assert (
            await client.post(f"{PLANS}/{pid}/revisions", headers=w["h"], json=body)
        ).status_code == 422
    same = await client.post(
        f"{PLANS}/{pid}/revisions",
        headers=w["h"],
        json={"changes": {"stop_loss": "4366.780"}, "reason": "nothing"},
    )
    assert same.status_code == 422 and same.json()["code"] == "no_changes"

    res = await client.post(
        f"{PLANS}/{pid}/revisions",
        headers=w["h"],
        json={"changes": change, "reason": "กลัว stop hunt ก่อนข่าว"},
    )
    assert res.status_code == 201, res.text
    rev = res.json()
    assert rev["revision_no"] == 2 and rev["changed_after_entry"] is False
    assert rev["changes"] == {"stop_loss": {"from": "4366.78", "to": "4360"}}
    assert rev["snapshot_hash"] != plan["lock_hash"]

    after = (await client.get(f"{PLANS}/{pid}", headers=w["h"])).json()
    # Before the entry the lot follows the 1% risk: wider SL → smaller lot.
    assert Decimal(after["stop_loss"]) == Decimal("4360")
    assert Decimal(after["planned_lot"]) == Decimal("0.36")
    assert after["lock_hash"] == plan["lock_hash"]  # the original lock stays
    assert after["current_hash"] == rev["snapshot_hash"] and after["current_revision"] == 2
    assert [r["revision_no"] for r in after["revisions"]] == [1, 2]
    listed = (await client.get(f"{PLANS}/{pid}/revisions", headers=w["h"])).json()
    assert [r["reason"] for r in listed] == [None, "กลัว stop hunt ก่อนข่าว"]

    async with app.state.engine.connect() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            await conn.execute(text("UPDATE trade_plan_revisions SET reason = 'x'"))


async def test_revision_after_entry_is_flagged(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-06 AC5: in the market the lot is fixed; widening SL adds risk and flags the revision."""
    w = await _world(client, app)
    plan = await _locked(client, w)
    pid = plan["id"]
    await _trigger(app, pid)

    preview = await client.post(
        f"{PLANS}/{pid}/revisions/preview", headers=w["h"], json={"changes": {"stop_loss": "4360"}}
    )
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["changed_after_entry"] is True and p["id"] is None
    # 0.48 lot x 6.78 x 100 = $325.44 more at risk ≈ +0.33R.
    assert Decimal(p["risk_delta_amount"]) == Decimal("325.44")
    assert Decimal(p["risk_delta_r"]) == Decimal("0.33")
    assert len((await client.get(f"{PLANS}/{pid}/revisions", headers=w["h"])).json()) == 1

    res = await client.post(
        f"{PLANS}/{pid}/revisions",
        headers=w["h"],
        json={"changes": {"stop_loss": "4360"}, "reason": "กลัว stop hunt"},
    )
    assert res.status_code == 201 and res.json()["changed_after_entry"] is True
    after = (await client.get(f"{PLANS}/{pid}", headers=w["h"])).json()
    assert after["status"] == "triggered"
    assert Decimal(after["planned_lot"]) == Decimal("0.48")
    assert Decimal(after["planned_risk_amount"]) == Decimal("1320.96")

    risk = await client.post(
        f"{PLANS}/{pid}/revisions",
        headers=w["h"],
        json={"changes": {"planned_risk_pct": "2"}, "reason": "x"},
    )
    assert risk.status_code == 422 and risk.json()["code"] == "risk_pct_after_entry"


# ------------------------------------------------------------------ AC6 states + expiry


async def test_status_changes_need_a_reason(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-06 AC6: skipped / missed / invalidated with a reason; illegal moves are 409."""
    w = await _world(client, app)
    draft = await _plan(client, w)
    url = f"{PLANS}/{draft['id']}/status"
    assert (await client.post(url, headers=w["h"], json={"status": "skipped"})).status_code == 422
    blank = await client.post(url, headers=w["h"], json={"status": "skipped", "reason": " "})
    assert blank.status_code == 422
    missed = await client.post(url, headers=w["h"], json={"status": "missed", "reason": "x"})
    assert missed.status_code == 409 and missed.json()["details"]["allowed_from"] == ["locked"]
    skipped = await client.post(url, headers=w["h"], json={"status": "skipped", "reason": "ข่าวแรง"})
    assert skipped.json()["status"] == "skipped" and skipped.json()["status_reason"] == "ข่าวแรง"
    again = await client.post(url, headers=w["h"], json={"status": "invalidated", "reason": "x"})
    assert again.status_code == 409

    locked = await _locked(client, w)
    res = await client.post(
        f"{PLANS}/{locked['id']}/status",
        headers=w["h"],
        json={"status": "missed", "reason": "ราคาไม่ถึง entry"},
    )
    assert res.json()["status"] == "missed"

    triggered = await _locked(client, w)
    await _trigger(app, triggered["id"])
    res = await client.post(
        f"{PLANS}/{triggered['id']}/status",
        headers=w["h"],
        json={"status": "invalidated", "reason": "x"},
    )
    assert res.status_code == 409
    no_types = await client.post(
        f"{PLANS}/{triggered['id']}/status",
        headers=w["h"],
        json={"status": "closed", "reason": "x"},
    )
    assert no_types.status_code == 422  # closed / triggered / expired are set by the system


async def test_expire_job(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-06 AC6: past valid_until without a trade → expired; a triggered plan is never expired."""
    w = await _world(client, app)
    draft = await _plan(client, w)
    locked = await _locked(client, w)
    triggered = await _locked(client, w)
    await _trigger(app, triggered["id"])
    future = await _plan(client, w, valid_until=(datetime.now(UTC) + timedelta(days=2)).isoformat())

    past = datetime.now(UTC) - timedelta(minutes=1)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text("UPDATE trade_plans SET valid_until = :t WHERE id = ANY(:ids)"),
            {"t": past, "ids": [uuid.UUID(p["id"]) for p in (draft, locked, triggered)]},
        )
    expired = await jobs.expire_plans({"sessionmaker": app.state.sessionmaker})
    assert expired == 2

    async with app.state.sessionmaker() as db:
        rows = (
            await db.execute(select(TradePlan.id, TradePlan.status, TradePlan.status_reason))
        ).all()
    by_id = {str(i): (s, r) for i, s, r in rows}
    assert by_id[draft["id"]] == ("expired", "valid_until_passed")
    assert by_id[locked["id"]] == ("expired", "valid_until_passed")
    assert by_id[triggered["id"]][0] == "triggered"
    assert by_id[future["id"]][0] == "draft"
    assert await jobs.expire_plans({"sessionmaker": app.state.sessionmaker}) == 0

    # A plan that can no longer be valid cannot be locked.
    stale = await _plan(client, w, valid_until=past.isoformat())
    await client.patch(
        f"{PLANS}/{stale['id']}", headers=w["h"], json={"checklist_answers": _tick_all(stale)}
    )
    res = await client.post(f"{PLANS}/{stale['id']}/lock", headers=w["h"])
    assert res.status_code == 422 and res.json()["code"] == "valid_until_passed"


async def test_default_valid_until_is_end_of_plan_day(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    w = await _world(client, app)  # user timezone Asia/Bangkok (+07:00)
    plan = await _plan(client, w)
    end = datetime.fromisoformat(plan["valid_until"]).astimezone(UTC)
    assert (end.hour, end.minute, end.second) == (16, 59, 59)
    assert plan["plan_date"] == w["analysis"]["analysis_date"]


# ------------------------------------------------------------------ AC7 pre-trade emotion


async def test_pre_trade_emotion(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-06 AC7 / F-11 AC1: mood, confidence and tags saved with the plan."""
    w = await _world(client, app)
    tags = {
        t["code"]: t["id"]
        for t in (await client.get("/api/v1/emotion-tags", headers=w["h"])).json()
    }
    emotion = {"mood": 7, "confidence": 6, "tags": [tags["confident"], tags["patient"]]}
    plan = await _plan(client, w, pre_emotion=emotion)
    assert plan["pre_emotion"]["mood"] == 7 and plan["pre_emotion"]["confidence"] == 6
    assert plan["pre_emotion"]["tags"] == [tags["confident"], tags["patient"]]

    bad = await client.post(PLANS, headers=w["h"], json=_plan_body(w, pre_emotion={"mood": 11}))
    assert bad.status_code == 422
    unknown = await client.put(
        f"{PLANS}/{plan['id']}/pre-emotion", headers=w["h"], json={"tags": [str(uuid.uuid4())]}
    )
    assert unknown.status_code == 422 and unknown.json()["code"] == "unknown_emotion_tag"
    res = await client.put(
        f"{PLANS}/{plan['id']}/pre-emotion",
        headers=w["h"],
        json={"mood": 4, "confidence": 8, "tags": [tags["fomo"]], "note": "อยากเข้าเร็ว"},
    )
    assert (
        res.json()["pre_emotion"]["mood"] == 4 and res.json()["pre_emotion"]["note"] == "อยากเข้าเร็ว"
    )


# ------------------------------------------------------------------ ownership / setup in use


async def test_setup_used_by_plan_cannot_be_deleted(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-04 AC2 with the real trade_plans FK (ON DELETE RESTRICT)."""
    w = await _world(client, app)
    await _plan(client, w)
    res = await client.delete(f"/api/v1/setups/{w['setup']['id']}", headers=w["h"])
    assert res.status_code == 409 and res.json()["code"] == "setup_in_use"
    await client.post(f"/api/v1/setups/{w['setup']['id']}/archive", headers=w["h"])
    archived = await client.post(PLANS, headers=w["h"], json=_plan_body(w))
    assert archived.status_code == 422 and archived.json()["code"] == "setup_archived"


async def test_other_users_plans_are_404(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    plan = await _plan(client, w)
    other = await _world(client, app, email="other@example.com")
    for method, url, body in (
        ("GET", f"{PLANS}/{plan['id']}", None),
        ("PATCH", f"{PLANS}/{plan['id']}", {"stop_loss": "4300"}),
        ("POST", f"{PLANS}/{plan['id']}/lock", None),
        ("POST", f"{PLANS}/{plan['id']}/status", {"status": "skipped", "reason": "x"}),
        ("GET", f"{PLANS}/{plan['id']}/revisions", None),
        ("DELETE", f"{PLANS}/{plan['id']}", None),
    ):
        res = await client.request(method, url, headers=other["h"], json=body)
        assert res.status_code == 404, (method, url)
    # Someone else's setup / account / analysis cannot be used either.
    for field in ("setup_id", "account_id", "analysis_id"):
        src = {
            "setup_id": w["setup"]["id"],
            "account_id": w["account"]["id"],
            "analysis_id": w["analysis"]["id"],
        }
        res = await client.post(
            PLANS, headers=other["h"], json=_plan_body(other, **{field: src[field]})
        )
        assert res.status_code == 404, field
    assert (await client.get(PLANS, headers=other["h"])).json() == []


async def test_draft_delete_only(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    draft = await _plan(client, w)
    locked = await _locked(client, w)
    assert (await client.delete(f"{PLANS}/{draft['id']}", headers=w["h"])).status_code == 204
    res = await client.delete(f"{PLANS}/{locked['id']}", headers=w["h"])
    assert res.status_code == 409


async def test_list_filters(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    a = await _plan(client, w)
    b = await _locked(client, w)
    day = w["analysis"]["analysis_date"]
    listed = (await client.get(PLANS, headers=w["h"], params={"date": day})).json()
    assert {p["id"] for p in listed} == {a["id"], b["id"]}
    locked = (await client.get(PLANS, headers=w["h"], params={"status": "locked"})).json()
    assert [p["id"] for p in locked] == [b["id"]]
    assert locked[0]["checklist"]["required_done"] == 2
    assert locked[0]["setup_name"] == "London Breakout" and locked[0]["symbol_code"] == "XAUUSD"
