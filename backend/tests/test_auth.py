"""FastAPI side of Better Auth (PLAN §5.3): JWT verification + live-session check.

F-01 AC6 — a deleted session (sign-out, device revoke, password reset) stops its JWT at once.
F-01 AC7 — every route except /health answers 401 without a valid session.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import timedelta
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI
from sqlalchemy import text

from app.core.security import RemoteJwks
from tests.conftest import TEST_JWKS, TEST_KID, TEST_SIGNING_KEY, auth, mint_token, signup

ME = "/api/v1/me"
# Not session-based: the cTrader OAuth callback is a browser redirect authenticated by its
# sealed one-time `state` (tests/test_ctrader.py::test_oauth_round_trip). `/ingest/events` is
# not listed: without its API key it answers 401 like everything else.
PUBLIC_PATHS = {"/api/v1/health", "/api/v1/connections/ctrader/callback"}


async def _status(client: httpx.AsyncClient, token: str) -> int:
    return (await client.get(ME, headers=auth(token))).status_code


async def test_valid_token_resolves_user(client: httpx.AsyncClient, app: FastAPI) -> None:
    body = await signup(app)
    res = await client.get(ME, headers=auth(body["access_token"]))
    assert res.status_code == 200
    assert res.json() == body["user"]


async def test_missing_or_malformed_credentials(client: httpx.AsyncClient) -> None:
    assert (await client.get(ME)).status_code == 401
    assert (await client.get(ME)).json() == {
        "code": "unauthorized",
        "message": "Not authenticated",
        "details": None,
    }
    for header in ("Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "Bearer "):
        res = await client.get(ME, headers={"Authorization": header})
        assert res.status_code == 401, header


@pytest.mark.parametrize(
    "case",
    ["expired", "wrong_issuer", "wrong_audience", "foreign_key", "unknown_kid", "no_sid", "hs256"],
)
async def test_rejected_tokens(client: httpx.AsyncClient, app: FastAPI, case: str) -> None:
    body = await signup(app)
    uid, sid = body["user"]["id"], body["session_id"]
    tokens: dict[str, str] = {
        "expired": mint_token(uid, sid, ttl=timedelta(seconds=-5)),
        "wrong_issuer": mint_token(uid, sid, iss="someone-else"),
        "wrong_audience": mint_token(uid, sid, aud="another-api"),
        # Same kid, different private key -> bad signature.
        "foreign_key": mint_token(uid, sid, key=Ed25519PrivateKey.generate()),
        "unknown_kid": mint_token(uid, sid, kid="rotated-away"),
        "no_sid": jwt.encode(
            {"sub": uid, "iss": "tracktrade-auth", "aud": "tracktrade-api", "iat": 1, "exp": 2**31},
            TEST_SIGNING_KEY,
            algorithm="EdDSA",
            headers={"kid": TEST_KID},
        ),
        # alg confusion: HMAC "signed" with the public key must never be accepted.
        "hs256": jwt.encode(
            {"sub": uid, "sid": str(sid)}, "x" * 32, algorithm="HS256", headers={"kid": TEST_KID}
        ),
    }
    res = await client.get(ME, headers=auth(tokens[case]))
    assert res.status_code == 401
    assert res.json()["code"] == "invalid_token"


async def test_revoked_session_stops_jwt_immediately(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """AC6: reset password / sign-out deletes the `auth_sessions` row -> unexpired JWT is dead."""
    body = await signup(app)
    assert await _status(client, body["access_token"]) == 200
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM auth_sessions WHERE id = :id"), {"id": body["session_id"]}
        )
    assert await _status(client, body["access_token"]) == 401


async def test_expired_session_is_rejected(client: httpx.AsyncClient, app: FastAPI) -> None:
    body = await signup(app)
    async with app.state.engine.begin() as conn:
        await conn.execute(
            text("UPDATE auth_sessions SET expires_at = now() - interval '1 second'")
        )
    assert await _status(client, body["access_token"]) == 401


async def test_session_of_another_user_is_rejected(client: httpx.AsyncClient, app: FastAPI) -> None:
    """A token pairing user B with user A's session id is invalid."""
    alice = await signup(app, "alice@example.com")
    bob = await signup(app, "bob@example.com")
    forged = mint_token(bob["user"]["id"], alice["session_id"])
    assert await _status(client, forged) == 401


def _protected_routes(app: FastAPI) -> list[tuple[str, str]]:
    """Every documented HTTP operation (the OpenAPI schema lists all included routers)."""
    paths: dict[str, dict[str, object]] = app.openapi()["paths"]
    return [
        (method.upper(), path)
        for path, operations in paths.items()
        if path not in PUBLIC_PATHS
        for method in operations
    ]


async def test_every_api_route_requires_a_session(client: httpx.AsyncClient, app: FastAPI) -> None:
    """AC7: walk the route table so new endpoints are covered automatically."""
    routes = _protected_routes(app)
    assert routes, "no routes found"
    for method, path in routes:
        url = path.replace("{", "").replace("}", "")  # placeholder values are fine: 401 comes first
        res = await client.request(method, url)
        assert res.status_code == 401, f"{method} {path} -> {res.status_code}"
    assert (await client.get("/api/v1/health")).status_code == 200


async def test_old_auth_endpoints_are_gone(client: httpx.AsyncClient) -> None:
    for path in ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"):
        assert (await client.post(path, json={})).status_code == 404


# ------------------------------------------------------------------ RemoteJwks


class _JwksServer:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, content=json.dumps(self.document))


async def test_remote_jwks_caches_and_refetches_on_rotation() -> None:
    server = _JwksServer({"keys": []})
    client = httpx.AsyncClient(transport=httpx.MockTransport(server.handler))
    jwks = RemoteJwks("http://auth/jwks", ttl=300, min_refetch=0, client=client)
    try:
        assert await jwks.get_key(TEST_KID) is None  # first fetch: empty set
        server.document = TEST_JWKS  # key appears (rotation)
        assert await jwks.get_key(TEST_KID) is not None  # unknown kid -> refetch
        calls = server.calls
        await jwks.get_key(TEST_KID)
        assert server.calls == calls  # served from cache
    finally:
        await jwks.aclose()


async def test_remote_jwks_throttles_unknown_kids() -> None:
    server = _JwksServer(TEST_JWKS)
    client = httpx.AsyncClient(transport=httpx.MockTransport(server.handler))
    jwks = RemoteJwks("http://auth/jwks", ttl=300, min_refetch=60, client=client)
    try:
        await jwks.get_key(TEST_KID)
        for _ in range(5):
            assert await jwks.get_key(f"garbage-{uuid.uuid4()}") is None
        assert server.calls == 1
    finally:
        await jwks.aclose()


async def test_remote_jwks_survives_auth_outage() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("auth service down")

    jwks = RemoteJwks(
        "http://auth/jwks", client=httpx.AsyncClient(transport=httpx.MockTransport(down))
    )
    try:
        started = time.monotonic()
        assert await jwks.get_key(TEST_KID) is None
        assert time.monotonic() - started < 2
    finally:
        await jwks.aclose()
