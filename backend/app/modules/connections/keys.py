"""Per-account API keys for the MT5 EA (F-08 AC1). Stored as sha256 only (NFR); the full key is
shown once when created / rotated (PLAN M13)."""

from __future__ import annotations

import hashlib
import secrets

PREFIX = "tt_live_"
HINT_PREFIX_LEN = len(PREFIX) + 4  # "tt_live_9f2c"


def new_key() -> str:
    return PREFIX + secrets.token_urlsafe(24)  # 32 url-safe chars, 192 bits


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def hint(prefix: str | None, last4: str | None) -> str | None:
    if not prefix or not last4:
        return None
    return f"{prefix}••••••••{last4}"


def looks_like_key(value: str | None) -> bool:
    return value is not None and value.startswith(PREFIX) and 20 <= len(value) <= 80
