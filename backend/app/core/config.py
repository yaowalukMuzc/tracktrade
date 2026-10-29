"""Application settings, read from environment variables (and `.env` in dev)."""

from __future__ import annotations

import re
from decimal import Decimal
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

    # Frontend origin — where the cTrader OAuth callback sends the browser back to.
    APP_URL: str = "http://localhost:5179"

    # Execution ingestion (Phase 4, F-07/F-08/F-10).
    RATE_LIMIT_INGEST: str = "120/min"  # per broker connection
    INGEST_MAX_BYTES: int = 2_000_000
    MATCH_TOLERANCE_SL: Decimal = Decimal("0.3")  # |fill - plan entry| <= 0.3 x SL distance (S3)
    OHLC_BARS_AROUND: int = 200  # bars requested before the entry / after the exit (F-08 AC5)
    MT5_STALE_SEC: int = 120  # no EA heartbeat for this long -> "not connected"
    MT5_EA_DIR: str = "../connectors/mt5-ea"  # zipped by GET /downloads/mt5-ea

    # Encrypts OAuth tokens at rest (NFR). Fernet key: `python -c "from cryptography.fernet
    # import Fernet; print(Fernet.generate_key().decode())"`. Empty -> cTrader linking is off.
    FERNET_KEY: str = ""
    # cTrader Open API app (https://openapi.ctrader.com/apps). Empty -> cTrader linking is off.
    CTRADER_CLIENT_ID: str = ""
    CTRADER_CLIENT_SECRET: str = ""
    CTRADER_REDIRECT_URI: str = "http://localhost:5179/api/v1/connections/ctrader/callback"
    CTRADER_AUTH_URL: str = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
    CTRADER_TOKEN_URL: str = "https://openapi.ctrader.com/apps/token"
    CTRADER_WS_LIVE: str = "wss://live.ctraderapi.com:5036"
    CTRADER_WS_DEMO: str = "wss://demo.ctraderapi.com:5036"
    CTRADER_HISTORY_DAYS: int = 90  # F-08 AC4

    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5179"]
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
