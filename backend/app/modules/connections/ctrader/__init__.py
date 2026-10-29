"""cTrader Open API connector (F-08 AC2, AC4): OAuth, history sync, real-time stream.

Uses the JSON-over-WebSocket transport (port 5036) so no protobuf toolchain is needed.
Status: built against the public Open API documentation and tested with fakes — not yet run
against a real cTrader app (needs CTRADER_CLIENT_ID / SECRET, PLAN R6).
"""
