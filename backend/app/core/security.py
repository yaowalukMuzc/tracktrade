"""Verification of the JWTs issued by the Better Auth service (PLAN §5.3).

The browser gets a 15-minute EdDSA JWT from `GET /api/auth/token`; FastAPI checks
its signature with the public keys from `GET /api/auth/jwks` (cached by `kid`),
plus issuer/audience/expiry. Whether the session behind the token (`sid`) is still
alive is checked against the database by the caller (`modules/auth/deps.py`).
FastAPI never issues tokens or handles passwords.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt

ALLOWED_ALGORITHMS = ("EdDSA",)


class InvalidToken(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID


class JwksProvider(Protocol):
    async def get_key(self, kid: str) -> jwt.PyJWK | None: ...

    async def aclose(self) -> None: ...


def _parse_jwks(document: Mapping[str, Any]) -> dict[str, jwt.PyJWK]:
    keys: dict[str, jwt.PyJWK] = {}
    for jwk in document.get("keys", []):
        kid = jwk.get("kid")
        if not kid:
            continue
        try:
            keys[kid] = jwt.PyJWK(dict(jwk))
        except jwt.PyJWTError:
            continue  # unsupported key type — skip it rather than fail every request
    return keys


class StaticJwks:
    """Fixed key set (tests, or a JWKS mounted from a file)."""

    def __init__(self, document: Mapping[str, Any]) -> None:
        self._keys = _parse_jwks(document)

    async def get_key(self, kid: str) -> jwt.PyJWK | None:
        return self._keys.get(kid)

    async def aclose(self) -> None:
        return None


class RemoteJwks:
    """JWKS fetched over HTTP and cached.

    Refetched when the cache is older than `ttl` or when an unknown `kid` shows up
    (key rotation) — but at most once per `min_refetch` seconds so garbage tokens
    cannot hammer the auth service.
    """

    def __init__(
        self,
        url: str,
        *,
        ttl: float = 300,
        min_refetch: float = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._url = url
        self._ttl = ttl
        self._min_refetch = min_refetch
        self._client = client or httpx.AsyncClient(timeout=5.0)
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def _refresh(self) -> None:
        res = await self._client.get(self._url)
        res.raise_for_status()
        self._keys = _parse_jwks(res.json())
        self._fetched_at = time.monotonic()

    async def get_key(self, kid: str) -> jwt.PyJWK | None:
        age = time.monotonic() - self._fetched_at
        if kid in self._keys and age < self._ttl:
            return self._keys[kid]
        async with self._lock:
            age = time.monotonic() - self._fetched_at
            stale = age >= self._ttl
            unknown = kid not in self._keys and age >= self._min_refetch
            if stale or unknown:
                try:
                    await self._refresh()
                except (httpx.HTTPError, ValueError):
                    # Auth service unreachable: keep serving cached keys.
                    self._fetched_at = time.monotonic() - self._ttl + self._min_refetch
        return self._keys.get(kid)

    async def aclose(self) -> None:
        await self._client.aclose()


async def decode_access_token(
    token: str, *, jwks: JwksProvider, issuer: str, audience: str
) -> AccessClaims:
    """Validate a Better Auth JWT and return its claims, else raise InvalidToken."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidToken("malformed token") from exc
    if header.get("alg") not in ALLOWED_ALGORITHMS:
        raise InvalidToken("algorithm not allowed")
    kid = header.get("kid")
    key = await jwks.get_key(kid) if isinstance(kid, str) else None
    if key is None:
        raise InvalidToken("unknown signing key")
    try:
        payload = jwt.decode(
            token,
            key=key,
            algorithms=list(ALLOWED_ALGORITHMS),
            issuer=issuer,
            audience=audience,
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    try:
        return AccessClaims(
            user_id=uuid.UUID(str(payload["sub"])), session_id=uuid.UUID(str(payload["sid"]))
        )
    except (KeyError, ValueError) as exc:
        raise InvalidToken("bad subject or session") from exc
