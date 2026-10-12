"""`WS /api/v1/ws?token=<access>` — per-user event stream.

Server -> client: `{type, data, ts}` events published to `user:{id}`.
Client -> server: `{"type": "ping"}` -> `{"type": "pong", "ts": ...}`.
Invalid/missing token -> close code 4401.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.logging import bind_user
from app.core.security import InvalidToken, decode_access_token
from app.modules.users.models import User
from app.realtime.hub import Hub

WS_UNAUTHORIZED = 4401

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None) -> None:
    settings: Settings = websocket.app.state.settings
    hub: Hub = websocket.app.state.hub
    sessionmaker: async_sessionmaker[AsyncSession] = websocket.app.state.sessionmaker

    user_id = None
    if token:
        try:
            user_id = decode_access_token(token, secret=settings.JWT_SECRET).user_id
        except InvalidToken:
            user_id = None
    if user_id is not None:
        async with sessionmaker() as session:
            if await session.get(User, user_id) is None:
                user_id = None
    if user_id is None:
        # Accept first so browsers actually receive the 4401 close code.
        await websocket.accept()
        await websocket.close(code=WS_UNAUTHORIZED, reason="unauthorized")
        return

    bind_user(str(user_id))
    await websocket.accept()
    await hub.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await websocket.send_json({"type": "pong", "ts": datetime.now(UTC).isoformat()})
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(user_id, websocket)
