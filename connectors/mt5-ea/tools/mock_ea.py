#!/usr/bin/env python3
"""Impersonate the TrackTrade MT5 EA for manual testing of the ingest API.

Standard library only. Sends PROTOCOL.md-shaped requests to
POST {url}/api/v1/ingest/events and prints the response JSON and the
round-trip time.

    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx open
    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx modify-sl
    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx close
    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx history
    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx heartbeat
    python mock_ea.py --url http://localhost:8001 --key tt_live_xxx duplicate

A small state file (mock_ea_state.json, next to this script) keeps the
ticket counter and the currently open mock position so that `open`,
`modify-sl` and `close` pair up.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid

EA_VERSION = "1.0.0-mock"
API_PATH = "/api/v1/ingest/events"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_ea_state.json")

SYMBOL = "XAUUSD.m"
DIGITS = 2


# --------------------------------------------------------------------------- helpers
def price(v: float) -> str:
    return f"{v:.{DIGITS}f}"


def money(v: float) -> str:
    s = f"{v:.2f}"
    return "0.00" if s == "-0.00" else s


def load_state() -> dict:
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"next_ticket": 900000000 + int(time.time()) % 1000000 * 100, "open": None}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def next_ticket(state: dict) -> int:
    t = int(state["next_ticket"])
    state["next_ticket"] = t + 1
    return t


def account(args) -> dict:
    return {
        "login": args.login,
        "server": "Mock-Demo",
        "company": "TrackTrade Mock Broker",
        "currency": "USD",
        "balance": "10000.00",
        "equity": "10000.00",
        "margin_mode": "hedging",
    }


def symbol_spec() -> dict:
    return {
        "name": SYMBOL,
        "digits": DIGITS,
        "point": "0.01",
        "contract_size": "100",
        "tick_size": "0.01",
        "tick_value": "1.00",
        "volume_step": "0.01",
        "volume_min": "0.01",
        "volume_max": "100",
        "currency_base": "XAU",
        "currency_profit": "USD",
    }


def deal(ticket: int, order: int, position_id: int, entry: str, side: str, volume: float,
         px: float, t: int, profit: float = 0.0, commission: float = 0.0,
         sl: float = 0.0, tp: float = 0.0, comment: str = "") -> dict:
    return {
        "ticket": str(ticket),
        "order": str(order),
        "position_id": str(position_id),
        "symbol": SYMBOL,
        "entry": entry,
        "type": side,
        "volume": f"{volume:.2f}",
        "price": price(px),
        "time": int(t),
        "commission": money(commission),
        "swap": "0.00",
        "fee": "0.00",
        "profit": money(profit),
        "sl": price(sl) if sl else "0",
        "tp": price(tp) if tp else "0",
        "magic": 0,
        "comment": comment,
    }


def position_snapshot(pos: dict | None) -> list:
    if not pos:
        return []
    return [{
        "position_id": str(pos["position_id"]),
        "symbol": SYMBOL,
        "type": pos["type"],
        "volume": f"{pos['volume']:.2f}",
        "price_open": price(pos["price"]),
        "sl": price(pos["sl"]) if pos["sl"] else "0",
        "tp": price(pos["tp"]) if pos["tp"] else "0",
        "time": int(pos["time"]),
    }]


def body(args, state: dict, **parts) -> dict:
    b = {
        "ea_version": EA_VERSION,
        "sent_at": int(time.time()),
        "account": account(args),
        "symbols": [symbol_spec()],
        "deals": [],
        "positions": position_snapshot(state.get("open")),
        "modifications": [],
        "ohlc": [],
    }
    b.update(parts)
    return b


def post(args, payload: dict, label: str = "") -> dict | None:
    url = args.url.rstrip("/") + API_PATH
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Api-Key": args.key,
        "User-Agent": f"TrackTrade-MT5-EA/{EA_VERSION}",
        "X-Request-Id": str(uuid.uuid4()),
    })
    if args.verbose:
        print(f"--> POST {url}\n{json.dumps(payload, indent=2, ensure_ascii=False)}")
    t0 = time.perf_counter()
    status, text, retry_after = 0, "", None
    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            status = resp.status
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status = e.code
        text = e.read().decode("utf-8", "replace")
        retry_after = e.headers.get("Retry-After")
    except urllib.error.URLError as e:
        ms = (time.perf_counter() - t0) * 1000
        print(f"{label}network error after {ms:.0f} ms: {e.reason}")
        return None
    ms = (time.perf_counter() - t0) * 1000
    extra = f"  Retry-After: {retry_after}" if retry_after else ""
    print(f"{label}HTTP {status}  {ms:.0f} ms{extra}")
    try:
        parsed = json.loads(text) if text else None
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        print(text)
        return None


# --------------------------------------------------------------------------- scenarios
def sc_open(args, state: dict) -> None:
    if state.get("open"):
        print(f"note: replacing the previously open mock position {state['open']['position_id']}")
    now = int(time.time())
    ticket = next_ticket(state)
    pos = {"position_id": ticket + 2, "order": ticket + 1, "type": "buy", "volume": 0.48,
           "price": 4387.60, "sl": 4380.00, "tp": 4400.00, "time": now}
    d = deal(ticket, pos["order"], pos["position_id"], "in", "buy", pos["volume"], pos["price"], now,
             commission=-3.36, sl=pos["sl"], tp=pos["tp"])
    state["next_ticket"] = ticket + 3
    state["open"] = pos
    save_state(state)
    post(args, body(args, state, deals=[d]), "open: ")


def sc_close(args, state: dict) -> None:
    pos = state.get("open")
    if not pos:
        print("no open mock position — run `open` first")
        return
    now = int(time.time())
    ticket = next_ticket(state)
    close_px = 4395.20
    profit = (close_px - pos["price"]) * pos["volume"] * 100 * (1 if pos["type"] == "buy" else -1)
    side = "sell" if pos["type"] == "buy" else "buy"
    d = deal(ticket, ticket + 1, pos["position_id"], "out", side, pos["volume"], close_px, now,
             profit=profit, commission=-3.36, sl=pos["sl"], tp=pos["tp"])
    state["next_ticket"] = ticket + 2
    state["open"] = None
    save_state(state)
    post(args, body(args, state, deals=[d]), "close: ")


def sc_modify_sl(args, state: dict) -> None:
    pos = state.get("open")
    if not pos:
        print("no open mock position — run `open` first")
        return
    now_ms = int(time.time() * 1000)
    old, new = pos["sl"], round(pos["sl"] - 5.0, DIGITS)
    mod = {
        "id": f"{pos['position_id']}:sl:{now_ms}",
        "position_id": str(pos["position_id"]),
        "field": "sl",
        "old": price(old) if old else "0",
        "new": price(new) if new else "0",
        "time": now_ms // 1000,
    }
    pos["sl"] = new
    save_state(state)
    post(args, body(args, state, modifications=[mod]), "modify-sl: ")


def sc_history(args, state: dict) -> None:
    """A few closed trades over the last 10 days, sent as two history chunks."""
    now = int(time.time())
    window_from = now - 10 * 86400
    deals = []
    base_px = 4300.0
    for i in range(6):
        t_open = window_from + (i + 1) * 86400 + 3600 * (i % 4)
        t_close = t_open + 1800 + 600 * i
        side = "buy" if i % 2 == 0 else "sell"
        close_side = "sell" if side == "buy" else "buy"
        vol = 0.10 + 0.05 * i
        px_in = base_px + 7.5 * i
        move = 6.0 if i % 3 != 2 else -4.0             # mostly winners, every third a loser
        px_out = px_in + move if side == "buy" else px_in - move
        profit = move * vol * 100
        t = next_ticket(state)              # in-deal ticket; t+1 position id, t+2 order
        pid = t + 1
        deals.append(deal(t, t + 2, pid, "in", side, vol, px_in, t_open,
                          commission=-vol * 7, sl=px_in - 8 if side == "buy" else px_in + 8,
                          tp=px_in + 12 if side == "buy" else px_in - 12))
        t2 = t + 3                          # out-deal ticket; t+4 order
        deals.append(deal(t2, t2 + 1, pid, "out", close_side, vol, px_out, t_close,
                          profit=profit, commission=-vol * 7))
        state["next_ticket"] = t + 5
    save_state(state)
    deals.sort(key=lambda d: d["time"])
    half = len(deals) // 2
    chunks = [deals[:half], deals[half:]]
    for n, chunk in enumerate(chunks):
        final = n == len(chunks) - 1
        h_from = window_from if n == 0 else chunk[0]["time"]
        h_to = now if final else chunk[-1]["time"]
        post(args, body(args, state, deals=chunk,
                        history={"from": h_from, "to": h_to, "final": final}),
             f"history chunk {n + 1}/{len(chunks)}: ")


def sc_heartbeat(args, state: dict) -> None:
    resp = post(args, body(args, state), "heartbeat: ")
    if resp and resp.get("commands"):
        print(f"{len(resp['commands'])} command(s) pending — a real EA would run them now")


def sc_duplicate(args, state: dict) -> None:
    now = int(time.time())
    t = next_ticket(state)
    state["next_ticket"] = t + 3
    save_state(state)
    d = deal(t, t + 1, t + 2, "in", "sell", 0.20, 4390.10, now, commission=-1.40)
    results = []
    for i in (1, 2):
        r = post(args, body(args, state, deals=[d]), f"duplicate send {i}/2: ")
        results.append(r)
    for i, r in enumerate(results, 1):
        if r:
            print(f"send {i}: accepted={r.get('accepted')} duplicates={r.get('duplicates')}")


SCENARIOS = {
    "open": sc_open,
    "close": sc_close,
    "modify-sl": sc_modify_sl,
    "history": sc_history,
    "heartbeat": sc_heartbeat,
    "duplicate": sc_duplicate,
}


def main() -> None:
    p = argparse.ArgumentParser(description="Impersonate the TrackTrade MT5 EA against a running API.")
    p.add_argument("--url", required=True, help="API base URL, e.g. http://localhost:8001")
    p.add_argument("--key", required=True, help="per-account API key (tt_live_...)")
    p.add_argument("--login", default="5120934", help="account login to report (default 5120934)")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds")
    p.add_argument("-v", "--verbose", action="store_true", help="print the request body")
    p.add_argument("scenario", choices=list(SCENARIOS), help="what to send")
    args = p.parse_args()
    state = load_state()
    SCENARIOS[args.scenario](args, state)


if __name__ == "__main__":
    main()
