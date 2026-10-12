"""Application settings, read from environment variables (and `.env` in dev)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
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


DEV_JWT_SECRET = "dev-insecure-change-me-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    ENV: Literal["dev", "test", "prod"] = "dev"
    DATABASE_URL: str = "postgresql+asyncpg://tracktrade:tracktrade@localhost:5432/tracktrade"
    REDIS_URL: str = "redis://localhost:6379/0"

    JWT_SECRET: str = Field(default=DEV_JWT_SECRET, min_length=32)
    ACCESS_TOKEN_TTL_MIN: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    # A token replayed within this many seconds of its own rotation is treated as a lost
    # response (reload/navigation aborted the refresh), not theft — see auth.service.refresh.
    REFRESH_REUSE_GRACE_SEC: int = 30

    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    COOKIE_SECURE: bool = False
    RATE_LIMIT_AUTH: str = "10/min"
    LOG_LEVEL: str = "INFO"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return value

    @field_validator("RATE_LIMIT_AUTH")
    @classmethod
    def _check_rate(cls, value: str) -> str:
        parse_rate(value)
        return value

    @model_validator(mode="after")
    def _prod_guards(self) -> Settings:
        if self.ENV == "prod" and self.JWT_SECRET == DEV_JWT_SECRET:
            raise ValueError("JWT_SECRET must be set in prod")
        return self

    @property
    def auth_rate(self) -> tuple[int, int]:
        return parse_rate(self.RATE_LIMIT_AUTH)


@lru_cache
def get_settings() -> Settings:
    return Settings()
