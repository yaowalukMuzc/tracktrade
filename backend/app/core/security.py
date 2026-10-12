"""Password hashing (argon2), access JWTs and opaque refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

_hasher = PasswordHasher()
# Pre-computed hash used to keep login timing constant for unknown emails.
_DUMMY_HASH = _hasher.hash("tracktrade-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


class InvalidToken(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AccessClaims:
    user_id: uuid.UUID
    session_id: uuid.UUID | None  # refresh-token family that minted this token


def create_access_token(
    user_id: uuid.UUID,
    *,
    secret: str,
    ttl: timedelta,
    session_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> str:
    issued = now or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(issued.timestamp()),
        "exp": int((issued + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    if session_id is not None:
        payload["sid"] = str(session_id)
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret: str) -> AccessClaims:
    """Validate an access token and return its claims, else raise InvalidToken."""
    try:
        payload = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise InvalidToken("wrong token type")
    try:
        user_id = uuid.UUID(str(payload["sub"]))
        sid = payload.get("sid")
        session_id = uuid.UUID(str(sid)) if sid else None
    except ValueError as exc:
        raise InvalidToken("bad subject") from exc
    return AccessClaims(user_id=user_id, session_id=session_id)


def new_refresh_token() -> str:
    """Opaque, URL-safe random token (only its sha256 is stored)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
