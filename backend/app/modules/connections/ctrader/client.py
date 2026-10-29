"""Minimal cTrader Open API client over JSON WebSocket.

Every request carries a `clientMsgId`; the matching response resolves its future. Pushed
messages (execution events, token invalidated, disconnect) go to `events`. A heartbeat is sent
every 10 s as the API requires.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

from app.modules.connections.ctrader import mapper
from app.modules.connections.ctrader import protocol as p

log = structlog.get_logger(__name__)

HEARTBEAT_S = 10
REQUEST_TIMEOUT_S = 20
# Access-token problems — reconnecting cannot fix them, the trader must re-link (design 24).
AUTH_ERROR_CODES = {
    "CH_ACCESS_TOKEN_INVALID",
    "OA_AUTH_TOKEN_EXPIRED",
    "ACCESS_TOKEN_INVALID",
    "INVALID_TOKEN",
    "CH_CTID_TRADER_ACCOUNT_NOT_FOUND",
    "invalid_grant",
}


class CTraderError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message

    @property
    def is_auth(self) -> bool:
        return self.code in AUTH_ERROR_CODES


class Transport(Protocol):
    async def send(self, message: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


Connector = Callable[[str], Awaitable[Transport]]


async def websocket_connect(url: str) -> Transport:  # pragma: no cover — real network
    import websockets

    ws = await websockets.connect(url, max_size=16 * 1024 * 1024, ping_interval=None)
    return ws  # type: ignore[return-value]


class CTraderClient:
    def __init__(self, transport: Transport, *, timeout: float = REQUEST_TIMEOUT_S) -> None:
        self._t = transport
        self._timeout = timeout
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self.events: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._reader: asyncio.Task[None] | None = None
        self._beat: asyncio.Task[None] | None = None
        self.closed = asyncio.Event()

    @classmethod
    async def open(cls, url: str, connector: Connector = websocket_connect) -> CTraderClient:
        client = cls(await connector(url))
        client.start()
        return client

    def start(self) -> None:
        self._reader = asyncio.create_task(self._read(), name="ctrader-read")
        self._beat = asyncio.create_task(self._heartbeat(), name="ctrader-heartbeat")

    async def close(self) -> None:
        for task in (self._beat, self._reader):
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        with contextlib.suppress(Exception):
            await self._t.close()
        self._fail_pending(CTraderError("DISCONNECTED", "connection closed"))
        self.closed.set()

    def _fail_pending(self, exc: Exception) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_S)
            await self._t.send(json.dumps({"payloadType": p.HEARTBEAT_EVENT, "payload": {}}))

    async def _read(self) -> None:
        try:
            while True:
                msg = json.loads(await self._t.recv())
                msg_id = msg.get("clientMsgId")
                if msg_id and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(msg)
                elif msg.get("payloadType") != p.HEARTBEAT_EVENT:
                    await self.events.put(msg)
        except Exception as exc:  # connection dropped
            self._fail_pending(CTraderError("DISCONNECTED", str(exc)))
            self.closed.set()

    async def request(self, payload_type: int, payload: dict[str, Any]) -> dict[str, Any]:
        msg_id = uuid.uuid4().hex
        fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[msg_id] = fut
        await self._t.send(
            json.dumps({"clientMsgId": msg_id, "payloadType": payload_type, "payload": payload})
        )
        try:
            msg = await asyncio.wait_for(fut, self._timeout)
        except TimeoutError as exc:
            self._pending.pop(msg_id, None)
            raise CTraderError("TIMEOUT", f"no answer to {payload_type}") from exc
        body: dict[str, Any] = msg.get("payload", {})
        if msg.get("payloadType") in p.ERROR_TYPES:
            raise CTraderError(
                str(body.get("errorCode", "ERROR")), str(body.get("description", ""))
            )
        return body

    # ---------------------------------------------------------------- calls

    async def app_auth(self, client_id: str, client_secret: str) -> None:
        await self.request(
            p.APPLICATION_AUTH_REQ, {"clientId": client_id, "clientSecret": client_secret}
        )

    async def accounts(self, access_token: str) -> list[dict[str, Any]]:
        res = await self.request(p.GET_ACCOUNTS_BY_ACCESS_TOKEN_REQ, {"accessToken": access_token})
        accounts: list[dict[str, Any]] = res.get("ctidTraderAccount", [])
        return accounts

    async def account_auth(self, ctid: int, access_token: str) -> None:
        await self.request(
            p.ACCOUNT_AUTH_REQ, {"ctidTraderAccountId": ctid, "accessToken": access_token}
        )

    async def trader(self, ctid: int) -> dict[str, Any]:
        trader: dict[str, Any] = (
            await self.request(p.TRADER_REQ, {"ctidTraderAccountId": ctid})
        ).get("trader", {})
        return trader

    async def symbols(self, ctid: int, ids: set[int]) -> dict[int, mapper.SymbolInfo]:
        if not ids:
            return {}
        light = await self.request(p.SYMBOLS_LIST_REQ, {"ctidTraderAccountId": ctid})
        names = {int(s["symbolId"]): s for s in light.get("symbol", [])}
        full = await self.request(
            p.SYMBOL_BY_ID_REQ, {"ctidTraderAccountId": ctid, "symbolId": sorted(ids)}
        )
        out = {}
        for s in full.get("symbol", []):
            info = mapper.symbol_info(names.get(int(s["symbolId"]), {}), s)
            out[info.symbol_id] = info
        return out

    async def deals(self, ctid: int, from_ms: int, to_ms: int) -> list[dict[str, Any]]:
        """All deals in [from, to], one week per request (API limit), following `hasMore`."""
        out: list[dict[str, Any]] = []
        start = from_ms
        while start < to_ms:
            end = min(start + p.MAX_DEAL_WINDOW_MS, to_ms)
            cursor_end = end
            while True:
                res = await self.request(
                    p.DEAL_LIST_REQ,
                    {
                        "ctidTraderAccountId": ctid,
                        "fromTimestamp": start,
                        "toTimestamp": cursor_end,
                    },
                )
                batch = res.get("deal", [])
                out.extend(batch)
                if not res.get("hasMore") or not batch:
                    break
                # Newest first within a page: continue below the oldest one seen.
                cursor_end = min(int(d["executionTimestamp"]) for d in batch) - 1
            start = end + 1
        unique = {str(d["dealId"]): d for d in out}
        return sorted(unique.values(), key=lambda d: int(d["executionTimestamp"]))

    async def reconcile(self, ctid: int) -> list[dict[str, Any]]:
        positions: list[dict[str, Any]] = (
            await self.request(p.RECONCILE_REQ, {"ctidTraderAccountId": ctid})
        ).get("position", [])
        return positions

    async def trendbars(
        self, ctid: int, symbol_id: int, timeframe: str, from_ms: int, to_ms: int
    ) -> list[dict[str, Any]]:
        bars: list[dict[str, Any]] = (
            await self.request(
                p.TRENDBARS_REQ,
                {
                    "ctidTraderAccountId": ctid,
                    "symbolId": symbol_id,
                    "period": p.PERIOD[timeframe],
                    "fromTimestamp": from_ms,
                    "toTimestamp": to_ms,
                },
            )
        ).get("trendbar", [])
        return bars
