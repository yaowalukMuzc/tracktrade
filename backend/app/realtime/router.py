"""`WS /api/v1/ws?token=<jwt>` — per-user event stream (token = Better Auth JWT).

Server -> client: `{type, data, ts}` events published to `user:{id}`.
Client -> server: `{"type": "ping"}` -> `{"type": "pong", "ts": ...}`.
Invalid/missing token -> close code 4401.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import Unauthorized
from app.core.logging import bind_user
from app.modules.auth.deps import authenticate
from app.realtime.hub import Hub

WS_UNAUTHORIZED = 4401

router = APIRouter(tags=["realtime"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str | None = None) -> None:
    hub: Hub = websocket.app.state.hub
    sessionmaker: async_sessionmaker[AsyncSession] = websocket.app.state.sessionmaker

    user_id = None
    if token:
        async with sessionmaker() as session:
            try:
                current = await authenticate(
                    token,
                    settings=websocket.app.state.settings,
                    jwks=websocket.app.state.jwks,
                    session=session,
                )
                user_id = current.user.id
            except Unauthorized:
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
