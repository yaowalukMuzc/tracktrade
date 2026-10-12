"""Per-process WebSocket registry + a single Redis pub/sub listener.

Any process (API or worker) publishes to `user:{id}` via `core.pubsub.publish`.
Each API process subscribes to a user's channel while that user has at least one
socket connected to it, and fans received messages out to those sockets.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections import defaultdict

import structlog
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from starlette.websockets import WebSocket

from app.core.pubsub import USER_CHANNEL_PREFIX, user_channel

log = structlog.get_logger(__name__)


class Hub:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._sockets: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._pubsub: PubSub | None = None
        self._task: asyncio.Task[None] | None = None
        # Private channel keeps the pub/sub connection subscribed (and readable)
        # even when no user is connected.
        self._control_channel = f"hub:{uuid.uuid4().hex}"

    async def start(self) -> None:
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self._control_channel)
        self._task = asyncio.create_task(self._listen(), name="realtime-hub")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        if self._pubsub is not None:
            await self._pubsub.aclose()  # type: ignore[no-untyped-call]
        self._task = None
        self._pubsub = None

    def connection_count(self, user_id: uuid.UUID | str) -> int:
        return len(self._sockets.get(str(user_id), ()))

    async def connect(self, user_id: uuid.UUID | str, websocket: WebSocket) -> None:
        key = str(user_id)
        async with self._lock:
            first = not self._sockets[key]
            self._sockets[key].add(websocket)
            if first and self._pubsub is not None:
                await self._pubsub.subscribe(user_channel(key))

    async def disconnect(self, user_id: uuid.UUID | str, websocket: WebSocket) -> None:
        key = str(user_id)
        async with self._lock:
            sockets = self._sockets.get(key)
            if sockets is None:
                return
            sockets.discard(websocket)
            if not sockets:
                del self._sockets[key]
                if self._pubsub is not None:
                    await self._pubsub.unsubscribe(user_channel(key))

    async def _listen(self) -> None:
        assert self._pubsub is not None
        while True:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # connection hiccup: log and keep the loop alive
                log.exception("hub_listen_error")
                await asyncio.sleep(1.0)
                continue
            if not message or message.get("type") != "message":
                continue
            channel = _decode(message["channel"])
            if channel.startswith(USER_CHANNEL_PREFIX):
                await self._fanout(
                    channel.removeprefix(USER_CHANNEL_PREFIX), _decode(message["data"])
                )

    async def _fanout(self, user_id: str, payload: str) -> None:
        for websocket in list(self._sockets.get(user_id, ())):
            try:
                await websocket.send_text(payload)
            except Exception:
                await self.disconnect(user_id, websocket)


def _decode(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value
