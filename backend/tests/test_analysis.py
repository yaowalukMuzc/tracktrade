"""Market analysis (F-05 AC1-AC2), chart drawings (F-19 AC3), mock OHLC, /today + /daily."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI

from app.modules.analysis.schemas import narrative_text
from tests.conftest import auth, signup
from tests.test_plans import _locked, _plan, _world

ANALYSES = "/api/v1/analyses"
DRAWINGS = "/api/v1/chart-drawings"

NARRATIVE: dict[str, Any] = {
    "type": "doc",
    "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Bias"}]},
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "DXY อ่อนตัว "},
                {"type": "text", "text": "ทองทำ higher low", "marks": [{"type": "bold"}]},
            ],
        },
        {"type": "paragraph"},
    ],
}


async def _user(app: FastAPI, email: str = "nook@example.com") -> dict[str, str]:
    return auth((await signup(app, email))["access_token"])


async def _symbols(client: httpx.AsyncClient, h: dict[str, str]) -> dict[str, str]:
    return {s["code"]: s["id"] for s in (await client.get("/api/v1/symbols", headers=h)).json()}


def _bangkok_today() -> str:
    return datetime.now(ZoneInfo("Asia/Bangkok")).date().isoformat()


async def test_create_analysis_with_all_fields(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-05 AC1: per symbol/day with HTF bias, key levels, TF, session, narrative, confidence."""
    h = await _user(app)
    sym = await _symbols(client, h)
    res = await client.post(
        ANALYSES,
        headers=h,
        json={
            "symbol_id": sym["XAUUSD"],
            "htf_bias": "bull",
            "timeframes": ["H4", "M15", "H4"],
            "session": "london",
            "confidence": 7,
            "narrative": NARRATIVE,
            "key_levels": [
                {"price": "4366", "kind": "support", "label": "H4 swing low"},
                {"price": "4388", "price_to": "4380", "kind": "zone", "label": "Demand H1"},
            ],
        },
    )
    assert res.status_code == 201, res.text
    a = res.json()
    assert a["analysis_date"] == _bangkok_today()  # user timezone decides "today"
    assert a["timeframes"] == ["H4", "M15"]
    assert a["key_levels"][1] == {
        "price": "4380",
        "price_to": "4388",
        "kind": "zone",
        "label": "Demand H1",
    }
    assert a["narrative"] == NARRATIVE
    assert a["narrative_text"] == "Bias\nDXY อ่อนตัว ทองทำ higher low"
    assert a["symbol_code"] == "XAUUSD" and a["plans"] == []

    for bad in (
        {"htf_bias": "up"},
        {"confidence": 11},
        {"narrative": {"type": "paragraph"}},
        {"key_levels": [{"price": "-1"}]},
        {"timeframes": ["H2"]},
    ):
        body = {"symbol_id": sym["XAUUSD"], "htf_bias": "bull", **bad}
        assert (await client.post(ANALYSES, headers=h, json=body)).status_code == 422, bad

    patched = await client.patch(
        f"{ANALYSES}/{a['id']}", headers=h, json={"htf_bias": "range", "session": None}
    )
    assert patched.json()["htf_bias"] == "range" and patched.json()["session"] is None
    assert patched.json()["confidence"] == 7  # untouched

    listed = (await client.get(ANALYSES, headers=h, params={"date": a["analysis_date"]})).json()
    assert [x["id"] for x in listed] == [a["id"]]
    yesterday = (date.fromisoformat(a["analysis_date"]) - timedelta(days=1)).isoformat()
    assert (await client.get(ANALYSES, headers=h, params={"date": yesterday})).json() == []


def test_narrative_text_extraction() -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "b"},
                ],
            },
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "c"}]}
                        ],
                    }
                ],
            },
        ],
    }
    assert narrative_text(doc) == "a\nb\nc"


async def test_analysis_with_plans_is_protected(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    await _plan(client, w)
    aid = w["analysis"]["id"]
    res = await client.patch(
        f"{ANALYSES}/{aid}", headers=w["h"], json={"symbol_id": w["symbols"]["EURUSD"]["id"]}
    )
    assert res.status_code == 409 and res.json()["code"] == "analysis_has_plans"
    assert (await client.delete(f"{ANALYSES}/{aid}", headers=w["h"])).status_code == 409


async def test_drawings_save_and_load(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-05 AC2 / F-19 AC3: lines, boxes, text, horizontal lines saved and loaded back."""
    w = await _world(client, app)
    aid = w["analysis"]["id"]
    t0 = 1_760_000_000
    drawings = [
        {
            "tool": "trendline",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "4360"}, {"time": t0 + 7200, "price": "4380"}],
        },
        {
            "tool": "ray",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "4370"}, {"time": t0 + 3600, "price": "4372"}],
        },
        {
            "tool": "horizontal",
            "timeframe": "H4",
            "points": [{"time": t0, "price": "4366"}],
            "style": {"color": "warning", "line": "dashed"},
        },
        {
            "tool": "rectangle",
            "timeframe": "M15",
            "points": [{"time": t0, "price": "4380"}, {"time": t0 + 900, "price": "4388"}],
            "style": {"color": "brand"},
        },
        {
            "tool": "text",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "4390"}],
            "text": "Demand",
        },
        {
            "tool": "measure",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "4366"}, {"time": t0 + 3600, "price": "4437.5"}],
        },
    ]
    q = {"owner_type": "analysis", "owner_id": aid}
    res = await client.put(DRAWINGS, headers=w["h"], params=q, json={"drawings": drawings})
    assert res.status_code == 200, res.text
    saved = res.json()
    assert [d["tool"] for d in saved] == [d["tool"] for d in drawings]
    assert saved[2]["style"] == {"color": "warning", "line": "dashed", "width": 1}
    assert saved[4]["text"] == "Demand"
    loaded = (await client.get(DRAWINGS, headers=w["h"], params=q)).json()
    assert loaded == saved

    # PUT replaces the whole set; client ids are kept.
    keep = {**saved[0], "points": saved[0]["points"]}
    res = await client.put(DRAWINGS, headers=w["h"], params=q, json={"drawings": [keep]})
    assert [d["id"] for d in res.json()] == [saved[0]["id"]]

    for bad in (
        {
            "tool": "horizontal",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "1"}, {"time": t0, "price": "2"}],
        },
        {"tool": "text", "timeframe": "H1", "points": [{"time": t0, "price": "1"}]},
        {"tool": "arrow", "timeframe": "H1", "points": [{"time": t0, "price": "1"}]},
        {
            "tool": "horizontal",
            "timeframe": "H1",
            "points": [{"time": t0, "price": "1"}],
            "style": {"color": "#ff0000"},
        },
    ):
        r = await client.put(DRAWINGS, headers=w["h"], params=q, json={"drawings": [bad]})
        assert r.status_code == 422, bad

    # Plans have drawings too; someone else's owner is 404.
    plan = await _plan(client, w)
    pq = {"owner_type": "plan", "owner_id": plan["id"]}
    assert (
        await client.put(DRAWINGS, headers=w["h"], params=pq, json={"drawings": drawings[:1]})
    ).status_code == 200
    other = await _user(app, "other@example.com")
    assert (await client.get(DRAWINGS, headers=other, params=q)).status_code == 404
    assert (
        await client.put(DRAWINGS, headers=other, params=q, json={"drawings": []})
    ).status_code == 404
    bad_owner = {"owner_type": "position", "owner_id": str(uuid.uuid4())}
    assert (await client.get(DRAWINGS, headers=w["h"], params=bad_owner)).status_code == 422


async def test_mock_ohlc(client: httpx.AsyncClient, app: FastAPI) -> None:
    """Synthetic bars until Phase 4: deterministic, valid OHLC, no weekend bars, near the plan."""
    w = await _world(client, app)
    await _plan(client, w)
    sym = w["symbols"]["XAUUSD"]["id"]
    to = int(datetime(2026, 10, 9, 12, tzinfo=UTC).timestamp())
    params = {"symbol_id": sym, "tf": "H1", "to": to, "count": 120}
    one = (await client.get("/api/v1/market-data/ohlc", headers=w["h"], params=params)).json()
    two = (await client.get("/api/v1/market-data/ohlc", headers=w["h"], params=params)).json()
    assert one == two and one["source"] == "mock" and one["digits"] == 2
    bars = one["bars"]
    assert len(bars) == 120 and bars[-1]["time"] == to
    times = [b["time"] for b in bars]
    assert times == sorted(times)
    for b in bars:
        o, hi, lo, c = (Decimal(b[k]) for k in ("open", "high", "low", "close"))
        assert lo <= min(o, c) <= max(o, c) <= hi
        assert datetime.fromtimestamp(b["time"], UTC).weekday() < 5
    closes = [Decimal(b["close"]) for b in bars]
    assert Decimal("4200") < min(closes) and max(closes) < Decimal("4600")  # around entry 4387.52

    eur = (
        await client.get(
            "/api/v1/market-data/ohlc",
            headers=w["h"],
            params={"symbol_id": w["symbols"]["EURUSD"]["id"], "tf": "D1", "count": 30},
        )
    ).json()
    assert eur["digits"] == 5 and len(eur["bars"]) == 30
    assert all(Decimal("1.0") < Decimal(b["close"]) < Decimal("1.2") for b in eur["bars"])
    bad = await client.get(
        "/api/v1/market-data/ohlc", headers=w["h"], params={"symbol_id": sym, "tf": "H2"}
    )
    assert bad.status_code == 422


async def test_today(client: httpx.AsyncClient, app: FastAPI) -> None:
    """Today: the day's analyses + plans, limits, todo; filtered by account (F-02 AC3)."""
    w = await _world(client, app)
    a = await _plan(client, w)
    b = await _locked(client, w)
    demo = (
        await client.post(
            "/api/v1/accounts",
            headers=w["h"],
            json={
                "name": "Demo",
                "broker": "IC Markets",
                "platform": "mt5",
                "account_type": "demo",
                "currency": "USD",
                "initial_balance": "10000",
            },
        )
    ).json()
    res = await client.get("/api/v1/today", headers=w["h"])
    assert res.status_code == 200, res.text
    t = res.json()
    assert t["date"] == _bangkok_today() and t["timezone"] == "Asia/Bangkok"
    assert [x["id"] for x in t["analyses"]] == [w["analysis"]["id"]]
    assert {p["id"] for p in t["plans"]} == {a["id"], b["id"]}
    assert {r["name"] for r in t["risk"]} == {"FTMO 100K", "Demo"}
    ftmo = next(r for r in t["risk"] if r["name"] == "FTMO 100K")
    assert ftmo["trades_today"] == {"used": "0", "limit": "5"}
    assert ftmo["daily_loss"]["limit"] == "3000.00"
    assert t["todo"] == {"pending_match": 0, "pending_review": 0, "inbox": 0}
    assert t["pnl"] == [] and t["daily"] is None

    only_demo = (
        await client.get("/api/v1/today", headers=w["h"], params={"account_id": demo["id"]})
    ).json()
    assert only_demo["plans"] == [] and [r["name"] for r in only_demo["risk"]] == ["Demo"]
    assert only_demo["analyses"] == []  # the analysis belongs to FTMO
    other = await _user(app, "other@example.com")
    res = await client.get("/api/v1/today", headers=other, params={"account_id": demo["id"]})
    assert res.status_code == 404


async def test_daily_mood(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-11 AC5 (optional daily mood): one entry per day, replaced on edit."""
    h = await _user(app)
    tags = {
        t["code"]: t["id"] for t in (await client.get("/api/v1/emotion-tags", headers=h)).json()
    }
    day = _bangkok_today()
    empty = (await client.get(f"/api/v1/daily/{day}", headers=h)).json()
    assert empty["mood"] is None and empty["logged_at"] is None
    res = await client.put(
        f"/api/v1/daily/{day}", headers=h, json={"mood": 7, "tags": [tags["focused"]]}
    )
    assert res.status_code == 200 and res.json()["mood"] == 7
    res = await client.put(f"/api/v1/daily/{day}", headers=h, json={"mood": 5, "note": "นอนน้อย"})
    assert res.json()["mood"] == 5 and res.json()["tags"] == [] and res.json()["note"] == "นอนน้อย"
    today = (await client.get("/api/v1/today", headers=h)).json()
    assert today["daily"]["mood"] == 5
    assert (
        await client.put(f"/api/v1/daily/{day}", headers=h, json={"mood": 0})
    ).status_code == 422
