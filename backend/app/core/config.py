"""Application settings, read from environment variables (and `.env` in dev)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_RATE_RE = re.compile(r"^\s*(\d+)\s*/\s*(sec|second|s|min|minute|m|hour|h)\s*$")
_PERIOD_SECONDS = {"sec": 1, "second": 1, "s": 1, "min": 60, "minute": 60, "m": 60}
_PERIOD_SECONDS |= {"hour": 3600, "h": 3600}


def parse_rate(value: str) -> tuple[int, int]:
    """Parse `"10/min"` into `(limit, window_seconds)`."""
    match = _RATE_RE.match(value)
    if not match:
        raise ValueError(f"invalid rate limit {value!r}; expected e.g. '10/min'")
    return int(match.group(1)), _PERIOD_SECONDS[match.group(2)]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    ENV: Literal["dev", "test", "prod"] = "dev"
    DATABASE_URL: str = "postgresql+asyncpg://tracktrade:tracktrade@localhost:5432/tracktrade"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Better Auth service (auth/) — JWT verification (PLAN §5.3).
    AUTH_JWKS_URL: str = "http://localhost:3000/api/auth/jwks"
    JWT_ISSUER: str = "tracktrade-auth"
    JWT_AUDIENCE: str = "tracktrade-api"
    JWKS_CACHE_SEC: int = 300

    # Attachments (PLAN §8.1 S5): local disk for now; an S3 backend plugs into core/storage.py.
    MEDIA_ROOT: str = "var/media"
    MAX_UPLOAD_MB: int = 10

    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5178"]
    )
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
