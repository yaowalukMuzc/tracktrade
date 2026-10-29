"""Symmetric encryption for secrets stored in the database (OAuth tokens — NFR "encrypt at rest").

Fernet = AES-128-CBC + HMAC-SHA256 with a timestamp; the key comes from `FERNET_KEY`.
"""

from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.errors import AppError


class CryptoNotConfigured(AppError):
    def __init__(self) -> None:
        super().__init__(
            "encryption_not_configured",
            "FERNET_KEY is not set on the server",
            status_code=503,
        )


class SecretBox:
    def __init__(self, key: str) -> None:
        if not key:
            raise CryptoNotConfigured()
        self._fernet = Fernet(key.encode())

    def seal(self, data: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(data, sort_keys=True).encode()).decode()

    def open(self, token: str) -> dict[str, Any]:
        try:
            value: dict[str, Any] = json.loads(self._fernet.decrypt(token.encode()))
        except InvalidToken as exc:
            raise AppError("secret_unreadable", "Stored secret cannot be decrypted") from exc
        return value
