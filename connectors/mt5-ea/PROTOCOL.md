# TrackTrade ingest protocol (MT5 EA → API) — v1

The EA pushes everything to one endpoint. The server is the source of truth for de-duplication,
so the EA may resend anything at any time (after a crash, a lost response, a restart).

```
POST {ApiUrl}/api/v1/ingest/events
X-Api-Key: tt_live_<32 chars>           (per trading account, created on the Accounts › Connections tab)
Content-Type: application/json
```

## Rules

| Rule | Detail |
|---|---|
| Numbers | Prices, volumes and money are **JSON strings** (`"4387.60"`) so nothing is lost to float rounding. Format with the symbol's digits (`DoubleToString(price, digits)`); money with 2 decimals; volume with 2. |
| Time | **Unix seconds, UTC** (integers). MT5 deal/position times are *server* time: convert with `offset = TimeTradeServer() - TimeGMT()` → `utc = server_time - offset`. |
| Ids | Tickets / position ids as **strings** (`"123456789"`). |
| Idempotency | Deals by `ticket`; modifications by `id`; bars by (symbol, timeframe, time); positions by `position_id`. Duplicates are counted and ignored. |
| Batch size | ≤ 500 deals, ≤ 500 modifications, ≤ 20 000 bars per request (body ≤ 2 MB). Split larger history into several requests. |
| Latency | A new deal or SL/TP change must be sent within **5 seconds** (spec F-08 AC1): send from `OnTradeTransaction` right away. |
| Heartbeat | Every **10 s** send a request with only `account` (+ anything queued). The response carries pending commands. |
| Failure | Network error / 5xx / 429 → keep the batch in a file queue and retry with backoff (1 s, 2 s, 4 s … max 60 s; honour `Retry-After` on 429). 401 → stop sending and show "API key ไม่ถูกต้อง / invalid API key" on the chart. 422 → log the response body and drop that batch (it will never succeed). |

## Request body

All keys except `ea_version` and `account` are optional (omit or send `[]`).

```jsonc
{
  "ea_version": "1.0.0",
  "sent_at": 1760004303,
  "account": {
    "login": "5120934",
    "server": "FTMO-Demo",
    "company": "FTMO S.R.O.",
    "currency": "USD",
    "balance": "101240.00",
    "equity": "101757.00",
    "margin_mode": "hedging"          // "hedging" | "netting"
  },
  // Spec of every symbol that appears in deals/positions/ohlc of this request (sent once per symbol per EA session is enough).
  "symbols": [
    {
      "name": "XAUUSD.m",
      "digits": 2,
      "point": "0.01",
      "contract_size": "100",
      "tick_size": "0.01",
      "tick_value": "1.00",            // SYMBOL_TRADE_TICK_VALUE (account currency, 1 lot, one tick_size move)
      "volume_step": "0.01",
      "volume_min": "0.01",
      "volume_max": "100",
      "currency_base": "XAU",
      "currency_profit": "USD"
    }
  ],
  // DEAL_TYPE_BUY / DEAL_TYPE_SELL only (skip balance, credit, commission-only deals).
  "deals": [
    {
      "ticket": "123456789",
      "order": "223456789",
      "position_id": "323456789",      // DEAL_POSITION_ID
      "symbol": "XAUUSD.m",
      "entry": "in",                   // in | out | inout | out_by   (DEAL_ENTRY_*)
      "type": "buy",                   // buy | sell                  (DEAL_TYPE_*)
      "volume": "0.48",
      "price": "4387.60",
      "time": 1760004301,              // UTC seconds (DEAL_TIME_MSC/1000 converted to UTC)
      "commission": "-3.36",           // signed, as MT5 reports (cost < 0)
      "swap": "0.00",
      "fee": "0.00",
      "profit": "0.00",                // DEAL_PROFIT (0 for entries)
      "sl": "4380.00",                 // DEAL_SL ("0" = none)
      "tp": "4400.00",                 // DEAL_TP ("0" = none)
      "magic": 0,
      "comment": ""
    }
  ],
  // Snapshot of ALL currently open positions (send on every heartbeat). Lets the server track current SL/TP.
  "positions": [
    {
      "position_id": "323456789",
      "symbol": "XAUUSD.m",
      "type": "buy",                   // buy | sell
      "volume": "0.48",
      "price_open": "4387.60",
      "sl": "4380.00",
      "tp": "4400.00",
      "time": 1760004301
    }
  ],
  // SL/TP changes of an open position (TRADE_TRANSACTION_POSITION or polling the open positions every second).
  "modifications": [
    {
      "id": "323456789:sl:1760004400123",   // position_id:field:time_msc — unique and stable
      "position_id": "323456789",
      "field": "sl",                   // sl | tp
      "old": "4380.00",                // "0" = was not set
      "new": "4375.00",                // "0" = removed
      "time": 1760004400
    }
  ],
  "ohlc": [
    {
      "symbol": "XAUUSD.m",
      "timeframe": "M1",               // M1 | M5 | M15 | M30 | H1 | H4 | D1
      "bars": [[1760004300, "4387.10", "4388.00", "4386.50", "4387.60", "120"]]   // [time, open, high, low, close, tick_volume]
    }
  ],
  // Only in history imports (first run or a "resync" command): the deal window covered by this request.
  "history": { "from": 1752228000, "to": 1760004303, "final": true }   // final=true on the last chunk
}
```

## Response 200

```jsonc
{
  "accepted":   { "deals": 1, "modifications": 0, "bars": 1 },
  "duplicates": { "deals": 0, "modifications": 0, "bars": 0 },
  "unknown_symbols": [],            // broker symbols the server could not map (user adds a mapping in the app)
  "server_time": 1760004303,
  "commands": [
    { "id": "6f1c…", "kind": "resync", "params": { "days": 90 } },
    { "id": "7a2d…", "kind": "ohlc", "params": { "symbol": "XAUUSD.m", "from": 1760000000, "to": 1760090000,
                                                  "timeframes": ["M1", "M5", "M15", "H1", "H4", "D1"] } }
  ]
}
```

A command is delivered once. The EA runs it and sends the result as ordinary batches:

| kind | EA does |
|---|---|
| `resync` | Re-send all deals of the last `params.days` days (with `history`, `final=true` on the last chunk). |
| `ohlc` | For each timeframe, `CopyRates(symbol, tf, from, to)` (whatever exists up to now) and send as `ohlc`. |

## Errors

`{ "code": "...", "message": "...", "details": ... }`

| HTTP | code | EA action |
|---|---|---|
| 401 | `invalid_api_key` | stop, show message, wait for the user to change the input |
| 413 | `payload_too_large` | split the batch |
| 422 | `validation_error` | log + drop the batch |
| 429 | `rate_limited` | wait `Retry-After` seconds |
| 5xx | — | retry with backoff |

## First run

1. No state file → history import: all deals of the last **90 days** (spec F-08 AC4), oldest first, ≤ 500 per request, `history.final=true` on the last.
2. Then live mode: `OnTradeTransaction` + 10 s heartbeat + 1 s retry timer.
3. State (last sent deal time, last known SL/TP per open position) lives in `MQL5/Files/TrackTrade/<login>.state`; the unsent queue in `MQL5/Files/TrackTrade/<login>.queue`.
