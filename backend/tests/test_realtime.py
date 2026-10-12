"""WebSocket `/api/v1/ws`: auth, ping/pong, Redis pub/sub fan-out, worker ping job.

WebSocket tests use Starlette's sync TestClient (it runs the app + its lifespan
in a background event loop), so they build their own app instance.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis.asyncio import Redis
from starlette.websockets import WebSocketDisconnect

from app.core.pubsub import publish, user_channel
from app.main import create_app
from app.realtime.router import WS_UNAUTHORIZED
from app.worker import jobs
from tests.conftest import TEST_REDIS_URL, make_settings, register_payload


@pytest.fixture
def ws_client() -> Iterator[TestClient]:
    app = create_app(make_settings())
    with TestClient(app) as tc:
        yield tc


def _register(tc: TestClient, email: str = "ws@example.com") -> tuple[str, str]:
    res = tc.post("/api/v1/auth/register", json=register_payload(email))
    assert res.status_code == 201, res.text
    body = res.json()
    return body["user"]["id"], body["access_token"]


async def _wait_subscribed(app: FastAPI, user_id: str) -> None:
    redis: Redis = app.state.redis
    for _ in range(100):
        counts = await redis.pubsub_numsub(user_channel(user_id))
        if counts and counts[0][1] >= 1:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("hub never subscribed to the user channel")


def test_ws_rejects_missing_or_invalid_token(ws_client: TestClient) -> None:
    for url in ("/api/v1/ws", "/api/v1/ws?token=not-a-jwt"):
        with ws_client.websocket_connect(url) as ws, pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == WS_UNAUTHORIZED


def test_ws_ping_pong(ws_client: TestClient) -> None:
    _, token = _register(ws_client)
    with ws_client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
        ws.send_json({"type": "ping"})
        msg = ws.receive_json()
        assert msg["type"] == "pong"
        assert msg["ts"]


def test_pubsub_fanout_reaches_socket(ws_client: TestClient) -> None:
    user_id, token = _register(ws_client)
    app: FastAPI = ws_client.app  # type: ignore[assignment]
    with (
        ws_client.websocket_connect(f"/api/v1/ws?token={token}") as ws1,
        ws_client.websocket_connect(f"/api/v1/ws?token={token}") as ws2,
    ):
        ws_client.portal.call(_wait_subscribed, app, user_id)  # type: ignore[union-attr]
        ws_client.portal.call(  # type: ignore[union-attr]
            publish, app.state.redis, user_id, "alert.created", {"id": 1}
        )
        for ws in (ws1, ws2):
            msg = ws.receive_json()
            assert msg["type"] == "alert.created"
            assert msg["data"] == {"id": 1}
            assert msg["ts"]


def test_other_users_events_are_not_delivered(ws_client: TestClient) -> None:
    alice_id, alice_token = _register(ws_client, "alice@example.com")
    bob_id, _ = _register(ws_client, "bob@example.com")
    app: FastAPI = ws_client.app  # type: ignore[assignment]
    with ws_client.websocket_connect(f"/api/v1/ws?token={alice_token}") as ws:
        ws_client.portal.call(_wait_subscribed, app, alice_id)  # type: ignore[union-attr]
        portal = ws_client.portal
        assert portal is not None
        portal.call(publish, app.state.redis, bob_id, "secret", None)
        portal.call(publish, app.state.redis, alice_id, "mine", None)
        assert ws.receive_json()["type"] == "mine"


async def test_worker_ping_job_publishes_to_user_channel() -> None:
    redis = Redis.from_url(TEST_REDIS_URL)
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(user_channel("u-1"))
        await pubsub.get_message(timeout=1.0)  # subscribe confirmation
        result = await jobs.ping({"redis": redis, "job_id": "job-1"}, "u-1")
        assert result == "pong"
        msg = None
        for _ in range(20):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if msg:
                break
        assert msg is not None
        event = json.loads(msg["data"])
        assert event["type"] == "worker.pong"
        assert event["data"] == {"job_id": "job-1"}
    finally:
        await pubsub.aclose()
        await redis.aclose()
