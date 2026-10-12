"""Redis pub/sub helpers. Each user has one channel: `user:{id}`.

Messages are JSON `{type, data, ts}`; the realtime hub forwards them verbatim
to every WebSocket the user has open (on any API process).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis

USER_CHANNEL_PREFIX = "user:"


def user_channel(user_id: uuid.UUID | str) -> str:
    return f"{USER_CHANNEL_PREFIX}{user_id}"


def make_event(type_: str, data: Any = None) -> dict[str, Any]:
    return {"type": type_, "data": data, "ts": datetime.now(UTC).isoformat()}


async def publish(redis: Redis, user_id: uuid.UUID | str, type_: str, data: Any = None) -> int:
    """Publish an event to a user's channel. Returns number of Redis subscribers."""
    payload = json.dumps(make_event(type_, data), default=str)
    return int(await redis.publish(user_channel(user_id), payload))
