"""Broker ingest + connections (F-08 AC1, AC3, AC5, AC6; F-10 via sync; NFR key hashing)."""

from __future__ import annotations

import asyncio
import io
import json
import time
import zipfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.pubsub import user_channel
from app.modules.connections import keys
from app.modules.connections.models import BrokerConnection
from app.modules.positions.models import Execution
from tests.conftest import auth, signup
from tests.test_plans import _locked, _world

INGEST = "/api/v1/ingest/events"
POS = "/api/v1/positions"
D = Decimal


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0) + timedelta(seconds=1)


async def _key(client: httpx.AsyncClient, w: dict[str, Any]) -> dict[str, Any]:
    res = await client.post(
        f"/api/v1/accounts/{w['account']['id']}/connections/mt5", headers=w["h"]
    )
    assert res.status_code == 201, res.text
    out: dict[str, Any] = res.json()
    return out


def _account(**over: Any) -> dict[str, Any]:
    return {
        "login": "5120934",
        "server": "FTMO-Demo",
        "currency": "USD",
        "balance": "101240.00",
        "equity": "101757.00",
        **over,
    }


XAU_SPEC = {
    "name": "XAUUSD.m",
    "digits": 2,
    "point": "0.01",
    "contract_size": "100",
    "tick_size": "0.01",
    "tick_value": "1",
}


def _deal(ticket: str, entry: str, t: datetime, **over: Any) -> dict[str, Any]:
    deal = {
        "ticket": ticket,
        "position_id": "P1",
        "symbol": "XAUUSD.m",
        "entry": entry,
        "type": "buy" if entry == "in" else "sell",
        "volume": "0.48",
        "price": "4387.60",
        "time": _ts(t),
        "commission": "-1.68",
        "sl": "4367.60",
        "tp": "4418.00",
    }
    deal.update(over)
    return deal


async def _post(client: httpx.AsyncClient, key: str, **body: Any) -> httpx.Response:
    payload = {"ea_version": "1.0.0", "account": _account(), **body}
    return await client.post(INGEST, headers={"X-Api-Key": key}, json=payload)


# ------------------------------------------------------------------ keys


async def test_key_shown_once_hashed_and_rotatable(
    client: httpx.AsyncClient, app: FastAPI, db: Any
) -> None:
    w = await _world(client, app)
    first = await _key(client, w)
    key = first["api_key"]
    assert key.startswith("tt_live_") and len(key) == 40
    conn = first["connection"]
    assert conn["status"] == "pending" and conn["key_hint"] == f"{key[:12]}••••••••{key[-4:]}"
    stored = await db.scalar(select(BrokerConnection.api_key_hash))
    assert stored == keys.hash_key(key) and key not in json.dumps(conn)
    # The list never returns the key.
    listed = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/connections", headers=w["h"])
    ).json()
    assert "api_key" not in listed[0]

    rotated = (await _key(client, w))["api_key"]
    assert rotated != key
    assert (await _post(client, key)).status_code == 401
    assert (await _post(client, rotated)).status_code == 200


async def test_manual_account_has_no_mt5_key(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    acc = (
        await client.post(
            "/api/v1/accounts",
            headers=w["h"],
            json={
                "name": "Demo",
                "broker": "-",
                "platform": "manual",
                "account_type": "demo",
                "currency": "USD",
                "initial_balance": "10000",
            },
        )
    ).json()
    res = await client.post(f"/api/v1/accounts/{acc['id']}/connections/mt5", headers=w["h"])
    assert res.status_code == 422 and res.json()["code"] == "platform_mismatch"


@pytest.mark.parametrize("key", [None, "nope", "tt_live_" + "x" * 32])
async def test_bad_key_401(client: httpx.AsyncClient, key: str | None) -> None:
    headers = {"X-Api-Key": key} if key else {}
    res = await client.post(INGEST, headers=headers, json={"account": _account()})
    assert res.status_code == 401 and res.json()["code"] == "invalid_api_key"


# ------------------------------------------------------------------ deals → positions


async def test_deal_flow_idempotent_matched_and_closed(
    client: httpx.AsyncClient, app: FastAPI, db: Any
) -> None:
    """Open → duplicate resend → SL widened → close: one position, matched to the locked plan."""
    w = await _world(client, app)
    plan = await _locked(client, w)
    key = (await _key(client, w))["api_key"]
    t = _now()

    res = await _post(
        client,
        key,
        symbols=[XAU_SPEC],
        deals=[_deal("D1", "in", t)],
        positions=[
            {
                "position_id": "P1",
                "symbol": "XAUUSD.m",
                "type": "buy",
                "volume": "0.48",
                "price_open": "4387.60",
                "sl": "4367.60",
                "tp": "4418.00",
                "time": _ts(t),
            }
        ],
    )
    assert res.status_code == 200, res.text
    out = res.json()
    assert out["accepted"]["deals"] == 1 and out["duplicates"]["deals"] == 0
    assert out["unknown_symbols"] == []

    # The EA resends after a lost response — nothing new (F-08 AC3).
    again = (await _post(client, key, deals=[_deal("D1", "in", t)])).json()
    assert (again["accepted"]["deals"], again["duplicates"]["deals"]) == (0, 1)
    assert await db.scalar(select(func.count()).select_from(Execution)) == 1

    pos = (await client.get(POS, headers=w["h"])).json()["items"]
    assert len(pos) == 1
    p = pos[0]
    assert (p["source"], p["status"], p["symbol_code"], p["direction"]) == (
        "mt5",
        "open",
        "XAUUSD",
        "long",
    )
    assert (p["match_status"], p["plan"]["id"]) == ("auto", plan["id"])
    assert (await client.get(f"/api/v1/plans/{plan['id']}", headers=w["h"])).json()[
        "status"
    ] == "triggered"

    # The EA's symbol spec became a mapping with the broker's tick value (PLAN R9).
    maps = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/symbol-overrides", headers=w["h"])
    ).json()
    assert [(m["broker_symbol"], m["symbol_code"], D(m["tick_value"])) for m in maps] == [
        ("XAUUSD.m", "XAUUSD", D("1"))
    ]

    # SL widened 4367.60 → 4360 = more risk.
    mod = {
        "id": "P1:sl:1",
        "position_id": "P1",
        "field": "sl",
        "old": "4367.60",
        "new": "4360.00",
        "time": _ts(t + timedelta(minutes=5)),
    }
    res = (await _post(client, key, modifications=[mod, mod])).json()
    assert (res["accepted"]["modifications"], res["duplicates"]["modifications"]) == (1, 1)

    close = _deal(
        "D2",
        "out",
        t + timedelta(minutes=30),
        price="4398.38",
        profit="517.44",
        commission="-1.68",
        sl="4360.00",
    )
    closed = (await _post(client, key, deals=[close])).json()
    assert closed["accepted"]["deals"] == 1
    detail = (await client.get(f"{POS}/{p['id']}", headers=w["h"])).json()
    assert detail["status"] == "closed"
    assert (D(detail["gross_pnl"]), D(detail["net_pnl"])) == (D("517.44"), D("514.08"))
    assert D(detail["initial_sl"]) == D("4367.60") and D(detail["current_sl"]) == D("4360")
    assert D(detail["r_multiple"]) == D("0.54")  # 514.08 / 960
    assert [(m["field"], m["direction_of_risk"]) for m in detail["modifications"]] == [
        ("sl", "increase")
    ]
    assert (await client.get(f"/api/v1/plans/{plan['id']}", headers=w["h"])).json()[
        "status"
    ] == "closed"

    # Closing asks the EA for bars around the trade (F-08 AC5) in that same response:
    # 7 timeframes now (+7 again once the bars after the exit exist).
    ohlc = [c for c in closed["commands"] if c["kind"] == "ohlc"]
    assert sorted(c["params"]["timeframes"][0] for c in ohlc) == sorted(
        ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]
    )
    assert all(c["params"]["symbol"] == "XAUUSD.m" for c in ohlc)
    assert (await _post(client, key)).json()["commands"] == []  # delivered once


async def test_bars_fill_mae_mfe_and_chart(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    t = datetime(2026, 10, 9, 3, 5, tzinfo=UTC)
    await _post(
        client,
        key,
        deals=[
            _deal("D1", "in", t),
            _deal("D2", "out", t + timedelta(minutes=3), price="4390.00", profit="115.20"),
        ],
    )
    base = _ts(t) - _ts(t) % 60
    bars = [
        [base + 60 * i, "4387.00", h, lo, "4388.00", "100"]
        for i, (h, lo) in enumerate(
            [("4388.5", "4386.0"), ("4391.0", "4384.1"), ("4392.2", "4387.0"), ("4390.5", "4389.0")]
        )
    ]
    res = (
        await _post(client, key, ohlc=[{"symbol": "XAUUSD.m", "timeframe": "M1", "bars": bars}])
    ).json()
    assert res["accepted"]["bars"] == 4
    again = (
        await _post(client, key, ohlc=[{"symbol": "XAUUSD.m", "timeframe": "M1", "bars": bars}])
    ).json()
    assert (again["accepted"]["bars"], again["duplicates"]["bars"]) == (0, 4)

    pos = (await client.get(POS, headers=w["h"])).json()["items"][0]
    detail = (await client.get(f"{POS}/{pos['id']}", headers=w["h"])).json()
    # Long from 4387.60: lowest 4384.1 (-3.5), highest 4392.2 (+4.6) during 03:05-03:08.
    assert (D(detail["mae"]), D(detail["mfe"])) == (D("3.5"), D("4.6"))
    assert D(detail["mae_r"]) == D("0.18")  # 3.5 / 20 = 0.175

    chart = (
        await client.get(
            "/api/v1/market-data/ohlc",
            headers=w["h"],
            params={
                "symbol_id": w["symbols"]["XAUUSD"]["id"],
                "tf": "M1",
                "to": base + 600,
                "count": 10,
            },
        )
    ).json()
    assert chart["source"] == "mt5" and len(chart["bars"]) == 4


async def test_unknown_symbol_reported(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    res = (await _post(client, key, deals=[_deal("D1", "in", _now(), symbol="US30.cash")])).json()
    assert res["unknown_symbols"] == ["US30.cash"] and res["accepted"]["deals"] == 0
    conns = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/connections", headers=w["h"])
    ).json()
    assert conns[0]["last_error"].startswith("unknown_symbols: US30.cash")
    jobs = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/ingestion-jobs", headers=w["h"])
    ).json()
    assert jobs[0]["status"] == "warning" and jobs[0]["stats"]["unknown_symbols"] == ["US30.cash"]


async def test_history_import_does_not_flood_match_queue(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """First-run import of old trades: no plans existed → recorded unplanned, not queued."""
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    start = _now() - timedelta(days=30)
    deals = []
    for i in range(3):
        t = start + timedelta(days=i)
        deals += [
            _deal(f"H{i}a", "in", t, position_id=f"HP{i}"),
            _deal(
                f"H{i}b",
                "out",
                t + timedelta(hours=1),
                position_id=f"HP{i}",
                price="4380.00",
                profit="-364.80",
            ),
        ]
    first = {
        "from": _ts(start - timedelta(days=60)),
        "to": _ts(start + timedelta(days=1)),
        "final": False,
    }
    last = {"from": _ts(start + timedelta(days=1)), "to": _ts(_now()), "final": True}
    assert (await _post(client, key, deals=deals[:2], history=first)).status_code == 200
    assert (await _post(client, key, deals=deals[2:], history=last)).status_code == 200

    page = (await client.get(POS, headers=w["h"])).json()
    assert page["counts"]["all"] == 3 and page["counts"]["pending"] == 0
    assert page["counts"]["unplanned"] == 3
    assert all(i["match_status"] == "auto" for i in page["items"])
    conn = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/connections", headers=w["h"])
    ).json()[0]
    assert conn["history_synced_at"] is not None and conn["stats"]["history_days"] == 90
    jobs = (
        await client.get(f"/api/v1/accounts/{w['account']['id']}/ingestion-jobs", headers=w["h"])
    ).json()
    assert [j["kind"] for j in jobs] == ["history", "history"]
    # Old trades get no OHLC requests (only the last 7 days do).
    assert (await _post(client, key)).json()["commands"] == []


async def test_live_trade_without_plan_waits_in_queue(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """Outside a history import the spec rule holds: no plan found → pending (F-10 AC2)."""
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    await _post(client, key, deals=[_deal("D1", "in", _now())])
    assert (await client.get(POS, headers=w["h"])).json()["counts"]["pending"] == 1


async def test_heartbeat_updates_status_balance_and_sync_now(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    w = await _world(client, app)
    made = await _key(client, w)
    key, conn_id = made["api_key"], made["connection"]["id"]
    assert (await _post(client, key)).status_code == 200
    acc = w["account"]["id"]
    conns = (await client.get(f"/api/v1/accounts/{acc}/connections", headers=w["h"])).json()
    assert conns[0]["status"] == "connected" and conns[0]["server"] == "FTMO-Demo"
    assert conns[0]["external_account_id"] == "5120934" and conns[0]["ea_version"] == "1.0.0"
    risk = (await client.get(f"/api/v1/accounts/{acc}/risk-status", headers=w["h"])).json()
    assert (D(risk["balance"]), D(risk["equity"])) == (D("101240"), D("101757"))
    assert D(
        (await client.get(f"/api/v1/accounts/{acc}", headers=w["h"])).json()["last_equity"]
    ) == D("101757")

    res = await client.post(f"/api/v1/connections/{conn_id}/sync", headers=w["h"])
    assert res.status_code == 202
    await client.post(f"/api/v1/connections/{conn_id}/sync", headers=w["h"])  # no duplicate
    cmds = (await _post(client, key)).json()["commands"]
    assert [(c["kind"], c["params"]) for c in cmds] == [("resync", {"days": 7})]


async def test_validation_and_size_limits(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    deal = _deal("D1", "in", _now())
    deal["price"] = 4387.6  # float, not a string
    res = await _post(client, key, deals=[deal])
    assert res.status_code == 422 and res.json()["code"] == "validation_error"
    res = await client.post(
        INGEST, headers={"X-Api-Key": key, "Content-Type": "application/json"}, content=b"{not json"
    )
    assert res.status_code == 422 and res.json()["code"] == "invalid_json"
    big = await client.post(INGEST, headers={"X-Api-Key": key}, content=b"x" * 2_000_001)
    assert big.status_code == 413


async def test_ingest_rate_limit(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    original = app.state.settings
    app.state.settings = original.model_copy(update={"RATE_LIMIT_INGEST": "2/min"})
    try:
        codes = [(await _post(client, key)).status_code for _ in range(3)]
    finally:
        app.state.settings = original
    assert codes == [200, 200, 429]


async def test_deal_reaches_websocket_within_5s(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-08 AC1 / NFR: event → server → user's channel well under 5 s."""
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    user_id = (await client.get("/api/v1/me", headers=w["h"])).json()["id"]
    pubsub = app.state.redis.pubsub()
    await pubsub.subscribe(user_channel(user_id))
    try:
        await pubsub.get_message(timeout=1)  # subscribe ack
        started = time.perf_counter()
        assert (await _post(client, key, deals=[_deal("D1", "in", _now())])).status_code == 200
        types: list[str] = []
        wanted = {"position.created", "sync.first_deal"}
        while time.perf_counter() - started < 5 and not wanted <= set(types):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg:
                types.append(json.loads(msg["data"])["type"])
        elapsed = time.perf_counter() - started
    finally:
        await pubsub.aclose()
    assert "position.created" in types and "sync.first_deal" in types
    assert elapsed < 5


async def test_connections_are_private(client: httpx.AsyncClient, app: FastAPI) -> None:
    a = await _world(client, app)
    conn = (await _key(client, a))["connection"]
    hb = auth((await signup(app, "b@example.com"))["access_token"])
    acc = a["account"]["id"]
    for method, path in [
        ("GET", f"/api/v1/accounts/{acc}/connections"),
        ("POST", f"/api/v1/accounts/{acc}/connections/mt5"),
        ("GET", f"/api/v1/accounts/{acc}/ingestion-jobs"),
        ("POST", f"/api/v1/connections/{conn['id']}/sync"),
        ("DELETE", f"/api/v1/connections/{conn['id']}"),
    ]:
        assert (await client.request(method, path, headers=hb)).status_code == 404, path
    for path in (f"/api/v1/accounts/{acc}/connections", "/api/v1/downloads/mt5-ea"):
        assert (await client.get(path)).status_code == 401


async def test_disconnect_keeps_trades(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    made = await _key(client, w)
    await _post(client, made["api_key"], deals=[_deal("D1", "in", _now())])
    res = await client.delete(f"/api/v1/connections/{made['connection']['id']}", headers=w["h"])
    assert res.status_code == 204
    assert (await _post(client, made["api_key"])).status_code == 401
    assert (await client.get(POS, headers=w["h"])).json()["total"] == 1


async def test_ea_download_zip(client: httpx.AsyncClient, app: FastAPI) -> None:
    w = await _world(client, app)
    res = await client.get("/api/v1/downloads/mt5-ea", headers=w["h"])
    assert res.status_code == 200 and res.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(res.content)).namelist()
    assert "TrackTrade/TrackTrade.mq5" in names and "TrackTrade/README.md" in names
    assert not any("tools" in n for n in names)


async def test_concurrent_duplicate_batches_store_once(
    client: httpx.AsyncClient, app: FastAPI, db: Any
) -> None:
    w = await _world(client, app)
    key = (await _key(client, w))["api_key"]
    batch = [_deal("D1", "in", _now())]
    results = await asyncio.gather(*[_post(client, key, deals=batch) for _ in range(4)])
    assert all(r.status_code == 200 for r in results)
    assert await db.scalar(select(func.count()).select_from(Execution)) == 1
    assert (await client.get(POS, headers=w["h"])).json()["total"] == 1
