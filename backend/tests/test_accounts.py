"""Accounts, risk profile + versions, rules, symbol mapping, audit log, risk calc API.

F-02 AC1 (CRUD + archive), AC2 (default risk profile), AC4 (audit + versioned snapshot),
F-03 AC2 (broker symbol mapping), F-01 AC4 (other users' rows are 404).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.modules.accounts.service import risk_profile_at
from tests.conftest import auth, signup

ACCOUNTS = "/api/v1/accounts"

FTMO: dict[str, Any] = {
    "name": "FTMO 100K Challenge",
    "broker": "FTMO",
    "platform": "mt5",
    "account_type": "prop",
    "account_number": "5120934",
    "currency": "USD",
    "initial_balance": "100000",
}


async def _user(app: FastAPI, email: str = "nook@example.com") -> dict[str, str]:
    return auth((await signup(app, email))["access_token"])


async def _account(
    client: httpx.AsyncClient, headers: dict[str, str], **overrides: Any
) -> dict[str, Any]:
    res = await client.post(ACCOUNTS, headers=headers, json={**FTMO, **overrides})
    assert res.status_code == 201, res.text
    body: dict[str, Any] = res.json()
    return body


async def test_create_account_gets_default_risk_profile(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    h = await _user(app)
    acc = await _account(client, h)
    assert acc["is_active"] is True
    assert Decimal(acc["initial_balance"]) == 100000

    profile = (await client.get(f"{ACCOUNTS}/{acc['id']}/risk-profile", headers=h)).json()
    assert {k: profile[k] for k in profile if k not in {"updated_at"}} == {
        "risk_per_trade_pct": "1.00",
        "max_daily_loss_pct": "3.00",
        "max_drawdown_pct": "10.00",
        "max_trades_per_day": 5,
        "revenge_cooldown_min": 30,
        "news_blackout_min": 15,
        "version": 1,
    }


async def test_create_with_custom_risk_profile(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    risk = {
        "risk_per_trade_pct": "0.5",
        "max_daily_loss_pct": "2",
        "max_drawdown_pct": "6",
        "max_trades_per_day": 3,
        "revenge_cooldown_min": 60,
        "news_blackout_min": 30,
    }
    acc = await _account(client, h, risk_profile=risk)
    profile = (await client.get(f"{ACCOUNTS}/{acc['id']}/risk-profile", headers=h)).json()
    assert profile["risk_per_trade_pct"] == "0.50"
    assert profile["max_trades_per_day"] == 3


@pytest.mark.parametrize(
    "patch",
    [
        {"platform": "ninja"},
        {"account_type": "paper"},
        {"currency": "usd"},
        {"initial_balance": "0"},
        {"name": "   "},
        {"is_active": False},  # not settable directly — use archive
    ],
)
async def test_account_validation(
    client: httpx.AsyncClient, app: FastAPI, patch: dict[str, Any]
) -> None:
    h = await _user(app)
    res = await client.post(ACCOUNTS, headers=h, json={**FTMO, **patch})
    assert res.status_code == 422


async def test_multiple_accounts_update_archive_unarchive(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    h = await _user(app)
    ftmo = await _account(client, h)
    demo = await _account(
        client, h, name="Demo Practice", platform="manual", account_type="demo",
        account_number=None, initial_balance="10517",
    )  # fmt: skip
    names = [a["name"] for a in (await client.get(ACCOUNTS, headers=h)).json()]
    assert names == ["FTMO 100K Challenge", "Demo Practice"]

    res = await client.patch(f"{ACCOUNTS}/{demo['id']}", headers=h, json={"name": "Demo 2"})
    assert res.json()["name"] == "Demo 2"

    archived = (await client.post(f"{ACCOUNTS}/{ftmo['id']}/archive", headers=h)).json()
    assert archived["is_active"] is False and archived["archived_at"]
    assert [a["id"] for a in (await client.get(ACCOUNTS, headers=h)).json()] == [demo["id"]]
    every = (await client.get(ACCOUNTS, headers=h, params={"include_archived": True})).json()
    assert {a["id"] for a in every} == {ftmo["id"], demo["id"]}
    # Archived data is still readable (history), and can come back.
    assert (await client.get(f"{ACCOUNTS}/{ftmo['id']}", headers=h)).status_code == 200
    back = (await client.post(f"{ACCOUNTS}/{ftmo['id']}/unarchive", headers=h)).json()
    assert back["is_active"] is True and back["archived_at"] is None


async def test_risk_profile_update_versions_and_audit(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """F-02 AC4: changes are audited; trades keep the version in force when they were opened."""
    h = await _user(app)
    acc = await _account(client, h)
    url = f"{ACCOUNTS}/{acc['id']}/risk-profile"
    opened_before_change = datetime.now(UTC)

    new = {
        "risk_per_trade_pct": "0.75",
        "max_daily_loss_pct": "3",
        "max_drawdown_pct": "10",
        "max_trades_per_day": 4,
        "revenge_cooldown_min": 30,
        "news_blackout_min": 15,
    }
    res = await client.put(url, headers=h, json=new)
    assert res.status_code == 200, res.text
    assert res.json()["version"] == 2
    # Same values again: no new version, no audit entry.
    assert (await client.put(url, headers=h, json=new)).json()["version"] == 2

    versions = (await client.get(f"{url}/versions", headers=h)).json()
    assert [(v["version"], v["risk_per_trade_pct"]) for v in versions] == [
        (2, "0.75"),
        (1, "1.00"),
    ]
    async with app.state.sessionmaker() as session:
        then = await risk_profile_at(session, uuid.UUID(acc["id"]), opened_before_change)
        now = await risk_profile_at(session, uuid.UUID(acc["id"]), datetime.now(UTC))
        early = await risk_profile_at(
            session, uuid.UUID(acc["id"]), opened_before_change - timedelta(days=30)
        )
    assert then is not None and then.version == 1 and then.risk_per_trade_pct == Decimal("1.00")
    assert now is not None and now.version == 2
    assert early is not None and early.version == 1  # imported older trade -> first version

    log = (await client.get(f"{ACCOUNTS}/{acc['id']}/audit-log", headers=h)).json()
    update = next(e for e in log if e["entity"] == "risk_profile" and e["action"] == "update")
    assert update["before"] == {"max_trades_per_day": 5, "risk_per_trade_pct": "1.00", "version": 1}
    assert update["after"] == {"max_trades_per_day": 4, "risk_per_trade_pct": "0.75", "version": 2}
    assert sum(e["action"] == "update" for e in log if e["entity"] == "risk_profile") == 1
    assert {("create", "trading_account"), ("create", "risk_profile")} <= {
        (e["action"], e["entity"]) for e in log
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"risk_per_trade_pct": "0"},
        {"risk_per_trade_pct": "11"},
        {"max_daily_loss_pct": "12"},  # above max drawdown 10
        {"max_trades_per_day": 0},
        {"news_blackout_min": -1},
    ],
)
async def test_risk_profile_validation(
    client: httpx.AsyncClient, app: FastAPI, bad: dict[str, Any]
) -> None:
    h = await _user(app)
    acc = await _account(client, h)
    body = {
        "risk_per_trade_pct": "1",
        "max_daily_loss_pct": "3",
        "max_drawdown_pct": "10",
        "max_trades_per_day": 5,
        "revenge_cooldown_min": 30,
        "news_blackout_min": 15,
        **bad,
    }
    res = await client.put(f"{ACCOUNTS}/{acc['id']}/risk-profile", headers=h, json=body)
    assert res.status_code == 422


async def test_risk_status_before_any_trade(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    acc = await _account(client, h)
    status = (await client.get(f"{ACCOUNTS}/{acc['id']}/risk-status", headers=h)).json()
    assert status["balance"] == "100000.00"
    assert status["daily_loss"] == {"used": "0", "limit": "3000.00"}
    assert status["trades_today"] == {"used": "0", "limit": "5"}


async def test_rules_crud(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    acc = await _account(client, h)
    url = f"{ACCOUNTS}/{acc['id']}/rules"
    friday = await client.post(
        url,
        headers=h,
        json={
            "code": "no_trading_window",
            "params": {"days": [4], "after": "20:00"},
            "severity": "high",
        },
    )
    assert friday.status_code == 201, friday.text
    lot = await client.post(
        url, headers=h, json={"code": "max_lot_vs_plan", "params": {"ratio": "1.2"}}
    )
    assert lot.json()["params"] == {"ratio": "1.2"}
    assert lot.json()["created_by"] == "trader"

    bad = [
        {"code": "no_trading_window", "params": {"days": [7], "after": "20:00"}},
        {"code": "no_trading_window", "params": {"days": [4], "after": "25:00"}},
        {"code": "max_lot_vs_plan", "params": {"ratio": "0.9"}},
        {"code": "teleport", "params": {}},
        {"code": "custom", "params": {"text": "x", "extra": 1}},
    ]
    for body in bad:
        assert (await client.post(url, headers=h, json=body)).status_code == 422, body

    rule_id = friday.json()["id"]
    off = await client.patch(f"{url}/{rule_id}", headers=h, json={"is_active": False})
    assert off.json()["is_active"] is False
    bad_patch = await client.patch(f"{url}/{rule_id}", headers=h, json={"params": {"days": []}})
    assert bad_patch.status_code == 422
    assert (await client.delete(f"{url}/{rule_id}", headers=h)).status_code == 204
    assert [r["code"] for r in (await client.get(url, headers=h)).json()] == ["max_lot_vs_plan"]


async def test_symbol_mapping_and_resolve(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-03 AC2: `XAUUSD.m` on this account means XAUUSD."""
    h = await _user(app)
    acc = await _account(client, h)
    symbols = {s["code"]: s for s in (await client.get("/api/v1/symbols", headers=h)).json()}
    url = f"{ACCOUNTS}/{acc['id']}/symbol-overrides"

    res = await client.put(
        url, headers=h,
        json={"broker_symbol": "GOLD.m", "symbol_id": symbols["XAUUSD"]["id"], "tick_value": "1"},
    )  # fmt: skip
    assert res.status_code == 200, res.text
    assert res.json()["symbol_code"] == "XAUUSD"
    # Same broker symbol (any case) replaces the mapping instead of duplicating it.
    res = await client.put(
        url, headers=h, json={"broker_symbol": "gold.M", "symbol_id": symbols["XAGUSD"]["id"]}
    )
    rows = (await client.get(url, headers=h)).json()
    assert len(rows) == 1 and rows[0]["symbol_code"] == "XAGUSD"

    resolve = f"{ACCOUNTS}/{acc['id']}/symbols/resolve"
    mapped = (await client.get(resolve, headers=h, params={"broker_symbol": "GOLD.m"})).json()
    assert (mapped["symbol_code"], mapped["source"]) == ("XAGUSD", "override")
    std = (await client.get(resolve, headers=h, params={"broker_symbol": "XAUUSD.m"})).json()
    assert (std["symbol_code"], std["source"]) == ("XAUUSD", "standard")
    unknown = await client.get(resolve, headers=h, params={"broker_symbol": "BTCUSD"})
    assert unknown.status_code == 404

    assert (await client.delete(f"{url}/{rows[0]['id']}", headers=h)).status_code == 204
    assert (await client.get(url, headers=h)).json() == []
    log = (await client.get(f"{ACCOUNTS}/{acc['id']}/audit-log", headers=h)).json()
    assert [e["action"] for e in log if e["entity"] == "account_symbol_override"] == [
        "delete",
        "update",
        "create",
    ]


async def test_risk_calc_endpoint(client: httpx.AsyncClient, app: FastAPI) -> None:
    h = await _user(app)
    acc = await _account(client, h)
    symbols = {s["code"]: s for s in (await client.get("/api/v1/symbols", headers=h)).json()}
    body = {
        "account_id": acc["id"],
        "symbol_id": symbols["XAUUSD"]["id"],
        "direction": "long",
        "entry": "4387.52",
        "stop_loss": "4377.52",
        "take_profits": [{"price": "4402.52", "pct": 50}, {"price": "4417.52", "pct": 50}],
    }
    res = await client.post("/api/v1/risk/calc", headers=h, json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    # Profile default 1% of $100,000 = $1,000 at a $10 stop on 100 oz -> 1 lot.
    assert (out["lot"], out["risk_amount"], out["rr_per_tp"], out["rr_avg"]) == (
        "1.00",
        "1000.00",
        ["1.50", "3.00"],
        "2.25",
    )

    cross = {**body, "symbol_id": symbols["GBPJPY"]["id"], "entry": "190", "stop_loss": "189.5"}
    cross["take_profits"] = []
    res = await client.post("/api/v1/risk/calc", headers=h, json=cross)
    assert res.status_code == 422
    assert res.json()["code"] == "conversion_rate_required"
    res = await client.post(
        "/api/v1/risk/calc", headers=h, json={**cross, "quote_to_account_rate": "0.00666666"}
    )
    assert res.json()["lot"] == "3.00"  # $1,000 / $333.33 per lot

    wrong = await client.post("/api/v1/risk/calc", headers=h, json={**body, "stop_loss": "4390"})
    assert wrong.json()["code"] == "stop_loss_wrong_side"


async def test_other_users_accounts_are_404(client: httpx.AsyncClient, app: FastAPI) -> None:
    """F-01 AC4 on every account endpoint."""
    alice = await _user(app, "alice@example.com")
    bob = await _user(app, "bob@example.com")
    acc = await _account(client, alice)
    rule = (
        await client.post(
            f"{ACCOUNTS}/{acc['id']}/rules",
            headers=alice,
            json={"code": "custom", "params": {"text": "No revenge trades"}},
        )
    ).json()
    base = f"{ACCOUNTS}/{acc['id']}"
    risk = {
        "risk_per_trade_pct": "1",
        "max_daily_loss_pct": "3",
        "max_drawdown_pct": "10",
        "max_trades_per_day": 5,
        "revenge_cooldown_min": 30,
        "news_blackout_min": 15,
    }
    calls = [
        ("GET", base, None),
        ("PATCH", base, {"name": "x"}),
        ("POST", f"{base}/archive", None),
        ("GET", f"{base}/risk-profile", None),
        ("PUT", f"{base}/risk-profile", risk),
        ("GET", f"{base}/risk-profile/versions", None),
        ("GET", f"{base}/risk-status", None),
        ("GET", f"{base}/rules", None),
        ("POST", f"{base}/rules", {"code": "custom", "params": {"text": "x"}}),
        ("PATCH", f"{base}/rules/{rule['id']}", {"is_active": False}),
        ("DELETE", f"{base}/rules/{rule['id']}", None),
        ("GET", f"{base}/symbol-overrides", None),
        ("GET", f"{base}/audit-log", None),
    ]
    for method, url, body in calls:
        res = await client.request(method, url, headers=bob, json=body)
        assert res.status_code == 404, f"{method} {url} -> {res.status_code}"
    assert (await client.get(ACCOUNTS, headers=bob)).json() == []
    # Alice's data is untouched.
    assert (await client.get(base, headers=alice)).json()["name"] == FTMO["name"]
    assert len((await client.get(f"{base}/rules", headers=alice)).json()) == 1
