# MT5 Expert Advisor (TrackTrade connector)

Placeholder — built in Phase 4 (spec F-08 AC1, PLAN §6 "connections / ingest").

The EA (`TrackTrade.mq5` + `include/*.mqh`) will push deals, positions, SL/TP modifications
and OHLC around trades to `POST /api/v1/ingest/events` with the per-account `X-Api-Key`,
and poll `GET /api/v1/ingest/commands` for resync requests.
