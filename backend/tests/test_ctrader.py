"""cTrader connector (F-08 AC2, AC4, NFR token encryption) against a fake Open API server."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from arq import Retry
from cryptography.fernet import Fernet
from fastapi import FastAPI
from sqlalchemy import select

from app.core.crypto import SecretBox
from app.core.effects import Effects
from app.modules.connections.ctrader import mapper, oauth, sync
from app.modules.connections.ctrader import protocol as p
from app.modules.connections.ctrader.client import CTraderClient
from app.modules.connections.models import BrokerConnection
from app.modules.connections.schemas import OpenPositionIn
from app.worker import jobs
from tests.conftest import auth, signup

D = Decimal
FERNET = Fernet.generate_key().decode()
XAU = mapper.SymbolInfo(symbol_id=41, name="XAUUSD", digits=2, lot_size=10_000)
T0 = datetime.now(UTC).replace(microsecond=0) - timedelta(days=2)
MS = int(T0.timestamp() * 1000)


# ------------------------------------------------------------------ mapper (pure)


def _entry(deal_id: int = 1, pos: int = 9, ms: int = MS) -> dict[str, Any]:
    return {
        "dealId": deal_id,
        "orderId": 5,
        "positionId": pos,
        "symbolId": 41,
        "tradeSide": p.BUY,
        "filledVolume": 4800,
        "volume": 4800,
        "executionPrice": 4387.6,
        "executionTimestamp": ms,
        "commission": -168,
        "moneyDigits": 2,
        "dealStatus": p.DEAL_FILLED,
    }


def _exit(deal_id: int = 2, pos: int = 9, ms: int = MS + 1_800_000) -> dict[str, Any]:
    return {
        **_entry(deal_id, pos, ms),
        "tradeSide": p.SELL,
        "executionPrice": 4398.38,
        "closePositionDetail": {"grossProfit": 51744, "swap": -120, "moneyDigits": 2},
    }


def test_deal_mapping_units() -> None:
    d = mapper.deal(_entry(), {41: XAU})
    assert d is not None
    assert (d.entry, d.type, d.volume, d.price, d.commission) == (
        "in",
        "buy",
        D("0.48"),
        D("4387.60"),
        D("-1.68"),
    )
    assert d.time == MS // 1000 and d.position_id == "9"
    x = mapper.deal(_exit(), {41: XAU})
    assert x is not None and (x.entry, x.profit, x.swap) == ("out", D("517.44"), D("-1.20"))
    assert mapper.deal({**_entry(), "dealStatus": 4}, {41: XAU}) is None  # rejected
    assert mapper.deal({**_entry(), "symbolId": 999}, {41: XAU}) is None


def test_position_and_modification_diff() -> None:
    raw = {
        "positionId": 9,
        "price": 4387.6,
        "stopLoss": 4367.6,
        "takeProfit": 4418.0,
        "tradeData": {"symbolId": 41, "volume": 4800, "tradeSide": p.BUY, "openTimestamp": MS},
    }
    before = mapper.position(raw, {41: XAU})
    after = mapper.position({**raw, "stopLoss": 4360.0}, {41: XAU})
    assert before is not None and after is not None
    mods = mapper.modifications(before, after, MS + 60_000)
    assert [(m.field, m.old, m.new) for m in mods] == [("sl", D("4367.60"), D("4360.00"))]
    assert mapper.modifications(None, after, MS) == []


def test_trendbars_relative_prices() -> None:
    bars = mapper.trendbars(
        [
            {
                "utcTimestampInMinutes": MS // 60000,
                "low": 438_410_000,
                "deltaOpen": 100_000,
                "deltaHigh": 810_000,
                "deltaClose": 300_000,
                "volume": 120,
            }
        ],
        "M1",
        XAU,
    )
    _, o, h, lo, c, v = bars.bars[0]
    assert (o, h, lo, c, v) == (D("4385.10"), D("4392.20"), D("4384.10"), D("4387.10"), D(120))


# ------------------------------------------------------------------ fake server


class FakeOpenApi:
    """Answers requests from canned handlers; tests can push execution events."""

    def __init__(self, handlers: dict[int, Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]]):
        self.handlers = handlers
        self.inbox: asyncio.Queue[str] = asyncio.Queue()
        self.sent: list[dict[str, Any]] = []

    async def send(self, message: str) -> None:
        msg = json.loads(message)
        self.sent.append(msg)
        if "clientMsgId" in msg:
            kind, body = self.handlers[msg["payloadType"]](msg["payload"])
            await self.inbox.put(
                json.dumps(
                    {"clientMsgId": msg["clientMsgId"], "payloadType": kind, "payload": body}
                )
            )

    async def recv(self) -> str:
        return await self.inbox.get()

    async def close(self) -> None:
        pass

    def push(self, kind: int, payload: dict[str, Any]) -> None:
        self.inbox.put_nowait(json.dumps({"payloadType": kind, "payload": payload}))

    async def connect(self, url: str) -> FakeOpenApi:
        self.url = url
        return self


def standard_handlers(
    deals: list[dict[str, Any]],
) -> dict[int, Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]]:
    return {
        p.APPLICATION_AUTH_REQ: lambda _: (p.APPLICATION_AUTH_RES, {}),
        p.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ: lambda _: (
            p.GET_ACCOUNTS_BY_ACCESS_TOKEN_RES,
            {
                "ctidTraderAccount": [
                    {"ctidTraderAccountId": 77, "isLive": True, "traderLogin": 8830211},
                    {"ctidTraderAccountId": 78, "isLive": False, "traderLogin": 1234},
                ]
            },
        ),
        p.ACCOUNT_AUTH_REQ: lambda _: (p.ACCOUNT_AUTH_RES, {}),
        p.DEAL_LIST_REQ: lambda req: (
            p.DEAL_LIST_RES,
            {
                "deal": [
                    d
                    for d in deals
                    if req["fromTimestamp"] <= d["executionTimestamp"] <= req["toTimestamp"]
                ],
                "hasMore": False,
            },
        ),
        p.RECONCILE_REQ: lambda _: (p.RECONCILE_RES, {"position": []}),
        p.SYMBOLS_LIST_REQ: lambda _: (
            p.SYMBOLS_LIST_RES,
            {"symbol": [{"symbolId": 41, "symbolName": "XAUUSD"}]},
        ),
        p.SYMBOL_BY_ID_REQ: lambda _: (
            p.SYMBOL_BY_ID_RES,
            {"symbol": [{"symbolId": 41, "digits": 2, "lotSize": 10_000}]},
        ),
        p.TRADER_REQ: lambda _: (p.TRADER_RES, {"trader": {"balance": 841_200, "moneyDigits": 2}}),
        p.TRENDBARS_REQ: lambda _: (p.TRENDBARS_RES, {"trendbar": []}),
    }


async def _ctrader_account(
    client: httpx.AsyncClient, app: FastAPI
) -> tuple[dict[str, str], dict[str, Any]]:
    h = auth((await signup(app, "ct@example.com"))["access_token"])
    acc = (
        await client.post(
            "/api/v1/accounts",
            headers=h,
            json={
                "name": "IC Markets Live",
                "broker": "IC Markets",
                "platform": "ctrader",
                "account_type": "live",
                "account_number": "8830211",
                "currency": "USD",
                "initial_balance": "8000",
            },
        )
    ).json()
    return h, acc


def _settings(app: FastAPI) -> Any:
    return app.state.settings.model_copy(
        update={"FERNET_KEY": FERNET, "CTRADER_CLIENT_ID": "cid", "CTRADER_CLIENT_SECRET": "secret"}
    )


async def _linked(app: FastAPI, account_id: str, expires_in: timedelta = timedelta(days=30)) -> str:
    box = SecretBox(FERNET)
    tokens = oauth.Tokens("acc-token", "ref-token", datetime.now(UTC) + expires_in)
    async with app.state.sessionmaker() as s, s.begin():
        conn = BrokerConnection(
            account_id=account_id,
            kind="ctrader_oauth",
            status="pending",
            oauth_tokens=tokens.sealed(box),
            token_expires_at=tokens.expires_at,
            external_meta={},
        )
        s.add(conn)
        await s.flush()
        return str(conn.id)


# ------------------------------------------------------------------ sync


async def test_history_sync_imports_deals_and_picks_account(
    client: httpx.AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-08 AC4: first sync imports 90 days; the cTrader login picks ctid 77 out of two."""
    monkeypatch.setattr(sync, "TRENDBAR_PAUSE_S", 0)
    h, acc = await _ctrader_account(client, app)
    conn_id = await _linked(app, acc["id"])
    old = MS - 80 * 86_400_000  # 80 days ago — inside the 90-day window
    fake = FakeOpenApi(
        standard_handlers([_entry(), _exit(), _entry(3, 10, old), _exit(4, 10, old + 60_000)])
    )
    settings = _settings(app)
    fx = Effects(redis=app.state.redis, queue=None)
    async with app.state.sessionmaker() as s:
        conn = await s.get(BrokerConnection, conn_id)
        result = await sync.sync_connection(
            s, fx, settings, conn, full_history=True, connector=fake.connect
        )
        await s.commit()
    assert result.deals == 4 and result.positions == 2
    assert fake.url == settings.CTRADER_WS_LIVE

    page = (await client.get("/api/v1/positions", headers=h)).json()
    assert page["counts"]["all"] == 2 and page["counts"]["pending"] == 0  # history → unplanned
    p0 = next(i for i in page["items"] if i["opened_at"].startswith(T0.date().isoformat()))
    assert (p0["source"], p0["status"], D(p0["net_pnl"])) == (
        "ctrader",
        "closed",
        D("512.88"),
    )  # 517.44 - 1.68 x 2 - 1.20 swap
    conns = (await client.get(f"/api/v1/accounts/{acc['id']}/connections", headers=h)).json()
    assert conns[0]["status"] == "connected" and conns[0]["external_account_id"] == "8830211"
    assert conns[0]["history_synced_at"] is not None
    st = (await client.get(f"/api/v1/accounts/{acc['id']}/risk-status", headers=h)).json()
    assert D(st["balance"]) == D("8412.00")
    # Tokens are encrypted at rest (NFR).
    async with app.state.sessionmaker() as s:
        raw = await s.scalar(
            select(BrokerConnection.oauth_tokens).where(BrokerConnection.id == conn_id)
        )
    assert raw is not None and "acc-token" not in raw

    # Second sync is incremental and idempotent.
    async with app.state.sessionmaker() as s:
        conn = await s.get(BrokerConnection, conn_id)
        again = await sync.sync_connection(
            s, fx, settings, conn, full_history=False, connector=fake.connect
        )
        await s.commit()
    assert again.deals == 0


async def test_expiring_token_is_refreshed(
    client: httpx.AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync, "TRENDBAR_PAUSE_S", 0)
    _, acc = await _ctrader_account(client, app)
    conn_id = await _linked(app, acc["id"], expires_in=timedelta(hours=1))
    seen: list[dict[str, list[str]]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(parse_qs(urlparse(str(req.url)).query))
        return httpx.Response(
            200, json={"accessToken": "new-acc", "refreshToken": "new-ref", "expiresIn": 2_628_000}
        )

    fake = FakeOpenApi(standard_handlers([]))
    async with (
        app.state.sessionmaker() as s,
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http,
    ):
        conn = await s.get(BrokerConnection, conn_id)
        await sync.sync_connection(
            s,
            Effects(redis=app.state.redis),
            _settings(app),
            conn,
            full_history=True,
            connector=fake.connect,
            http=http,
        )
        await s.commit()
        tokens = oauth.Tokens.unsealed(SecretBox(FERNET), conn.oauth_tokens or "")
    assert seen[0]["grant_type"] == ["refresh_token"] and seen[0]["refresh_token"] == ["ref-token"]
    assert tokens.access_token == "new-acc"
    auth_msgs = [m for m in fake.sent if m.get("payloadType") == p.ACCOUNT_AUTH_REQ]
    assert auth_msgs[0]["payload"]["accessToken"] == "new-acc"


def _worker_ctx(app: FastAPI, connector: Any, job_try: int) -> dict[str, Any]:
    return {
        "sessionmaker": app.state.sessionmaker,
        "settings": _settings(app),
        "redis": app.state.queue,
        "job_try": job_try,
        "ctrader_connector": connector,
    }


async def test_invalid_token_marks_error_without_retry(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """Design 24: "OAuth token หมดอายุ · 401 invalid_grant" + a failed history entry."""
    h, acc = await _ctrader_account(client, app)
    conn_id = await _linked(app, acc["id"])
    handlers = standard_handlers([])
    handlers[p.ACCOUNT_AUTH_REQ] = lambda _: (
        p.OA_ERROR_RES,
        {"errorCode": "CH_ACCESS_TOKEN_INVALID", "description": "Invalid access token"},
    )
    fake = FakeOpenApi(handlers)
    assert await jobs.sync_ctrader(_worker_ctx(app, fake.connect, 1), conn_id) == "error"
    conn = (await client.get(f"/api/v1/accounts/{acc['id']}/connections", headers=h)).json()[0]
    assert conn["status"] == "error" and conn["last_error"].startswith("CH_ACCESS_TOKEN_INVALID")
    jobs_ = (await client.get(f"/api/v1/accounts/{acc['id']}/ingestion-jobs", headers=h)).json()
    assert (jobs_[0]["status"], jobs_[0]["attempts"], jobs_[0]["source"]) == ("error", 1, "ctrader")


async def test_network_error_retries_then_fails(client: httpx.AsyncClient, app: FastAPI) -> None:
    h, acc = await _ctrader_account(client, app)
    conn_id = await _linked(app, acc["id"])

    async def down(url: str) -> Any:
        raise OSError("connection refused")

    with pytest.raises(Retry):
        await jobs.sync_ctrader(_worker_ctx(app, down, 1), conn_id)
    assert await jobs.sync_ctrader(_worker_ctx(app, down, 3), conn_id) == "error"
    jobs_ = (await client.get(f"/api/v1/accounts/{acc['id']}/ingestion-jobs", headers=h)).json()
    assert jobs_[0]["attempts"] == 3 and jobs_[0]["status"] == "error"


async def test_live_execution_events(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-08 AC2: pushed deal → position; pushed SL change → modification with risk direction."""
    h, acc = await _ctrader_account(client, app)
    conn_id = await _linked(app, acc["id"])
    settings, fx = _settings(app), Effects(redis=app.state.redis)
    snapshot = {
        "positionId": 9,
        "price": 4387.6,
        "stopLoss": 4367.6,
        "takeProfit": 4418.0,
        "tradeData": {"symbolId": 41, "volume": 4800, "tradeSide": p.BUY, "openTimestamp": MS},
    }
    events = [
        {"payloadType": p.EXECUTION_EVENT, "payload": {"deal": _entry(), "position": snapshot}},
        {
            "payloadType": p.EXECUTION_EVENT,
            "payload": {
                "position": {**snapshot, "stopLoss": 4360.0, "utcLastUpdateTimestamp": MS + 300_000}
            },
        },
        {"payloadType": p.HEARTBEAT_EVENT, "payload": {}},
    ]
    used = []
    for msg in events:
        async with app.state.sessionmaker() as s:
            conn = await s.get(BrokerConnection, conn_id)
            used.append(await sync.handle_event(s, fx, settings, conn, msg, {41: XAU}, "8830211"))
            await s.commit()
    assert used == [True, True, False]
    pos = (await client.get("/api/v1/positions", headers=h)).json()["items"][0]
    detail = (await client.get(f"/api/v1/positions/{pos['id']}", headers=h)).json()
    assert detail["source"] == "ctrader" and D(detail["current_sl"]) == D("4360")
    assert [(m["field"], m["direction_of_risk"]) for m in detail["modifications"]] == [
        ("sl", "increase")
    ]


async def test_client_correlates_and_surfaces_errors() -> None:
    fake = FakeOpenApi({p.TRADER_REQ: lambda _: (p.OA_ERROR_RES, {"errorCode": "INVALID_REQUEST"})})
    client = await CTraderClient.open("wss://x", fake.connect)
    try:
        with pytest.raises(Exception, match="INVALID_REQUEST"):
            await client.trader(1)
        fake.push(p.EXECUTION_EVENT, {"deal": {}})
        assert (await asyncio.wait_for(client.events.get(), 1))["payloadType"] == p.EXECUTION_EVENT
    finally:
        await client.close()


# ------------------------------------------------------------------ OAuth endpoints


async def test_authorize_needs_config_and_ctrader_account(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    h, acc = await _ctrader_account(client, app)
    url = f"/api/v1/accounts/{acc['id']}/connections/ctrader/authorize"
    res = await client.post(url, headers=h)
    assert res.status_code == 503 and res.json()["code"] == "ctrader_not_configured"


async def test_oauth_round_trip(
    client: httpx.AsyncClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    h, acc = await _ctrader_account(client, app)
    original = app.state.settings
    app.state.settings = _settings(app)
    try:
        res = await client.post(
            f"/api/v1/accounts/{acc['id']}/connections/ctrader/authorize", headers=h
        )
        assert res.status_code == 200, res.text
        query = parse_qs(urlparse(res.json()["authorize_url"]).query)
        assert query["client_id"] == ["cid"] and query["scope"] == ["trading"]
        state = query["state"][0]

        async def fake_exchange(settings: Any, http: Any, code: str) -> oauth.Tokens:
            assert code == "the-code"
            return oauth.Tokens("acc", "ref", datetime.now(UTC) + timedelta(days=30))

        monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
        cb = "/api/v1/connections/ctrader/callback"
        res = await client.get(cb, params={"code": "the-code", "state": state})
        assert res.status_code == 303
        assert res.headers["location"].endswith(
            f"account={acc['id']}&tab=connections&ctrader=connected"
        )
        # One-time state: replay is refused.
        replay = await client.get(cb, params={"code": "the-code", "state": state})
        assert "ctrader=error&reason=invalid_state" in replay.headers["location"]
        forged = await client.get(cb, params={"code": "x", "state": "garbage"})
        assert "reason=invalid_state" in forged.headers["location"]
    finally:
        app.state.settings = original
    conns = (await client.get(f"/api/v1/accounts/{acc['id']}/connections", headers=h)).json()
    assert [(c["kind"], c["status"]) for c in conns] == [("ctrader_oauth", "pending")]


async def test_open_position_model_roundtrip() -> None:
    o = OpenPositionIn(
        position_id="9",
        symbol="XAUUSD",
        type="buy",
        volume=D("0.48"),
        price_open=D("4387.6"),
        sl=D("4367.6"),
        tp=D("0"),
    )
    assert OpenPositionIn.model_validate(o.model_dump(mode="json")) == o
