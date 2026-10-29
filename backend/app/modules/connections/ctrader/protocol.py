"""Open API message ids and enums used here (OpenApiMessages.proto / OpenApiModelMessages.proto).

Values follow the published proto definitions; re-check them against the current spotware
`openapi-proto-messages` release when the app credentials arrive.
"""

from __future__ import annotations

HEARTBEAT_EVENT = 51
ERROR_RES = 50  # ProtoErrorRes (common)

APPLICATION_AUTH_REQ = 2100
APPLICATION_AUTH_RES = 2101
ACCOUNT_AUTH_REQ = 2102
ACCOUNT_AUTH_RES = 2103
SYMBOLS_LIST_REQ = 2114
SYMBOLS_LIST_RES = 2115
SYMBOL_BY_ID_REQ = 2116
SYMBOL_BY_ID_RES = 2117
TRADER_REQ = 2121
TRADER_RES = 2122
RECONCILE_REQ = 2124
RECONCILE_RES = 2125
EXECUTION_EVENT = 2126
DEAL_LIST_REQ = 2133
DEAL_LIST_RES = 2134
TRENDBARS_REQ = 2137
TRENDBARS_RES = 2138
OA_ERROR_RES = 2142
ACCOUNTS_TOKEN_INVALIDATED_EVENT = 2147
CLIENT_DISCONNECT_EVENT = 2148
GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ = 2149
GET_ACCOUNTS_BY_ACCESS_TOKEN_RES = 2150

ERROR_TYPES = {ERROR_RES, OA_ERROR_RES}

# ProtoOATradeSide
BUY, SELL = 1, 2
# ProtoOADealStatus — only filled deals move a position.
DEAL_FILLED, DEAL_PARTIALLY_FILLED = 2, 3
# ProtoOATrendbarPeriod
PERIOD = {"M1": 1, "M5": 5, "M15": 7, "M30": 8, "H1": 9, "H4": 10, "D1": 12}
# Relative prices (trendbars, some fields) are integers in 1/100 000 of a price unit.
PRICE_SCALE = 100_000
# Deal list requests may span at most one week.
MAX_DEAL_WINDOW_MS = 7 * 24 * 3600 * 1000
