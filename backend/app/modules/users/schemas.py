from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Locale = Literal["th", "en"]
Theme = Literal["light", "dark", "system"]

_TIMEZONES = frozenset(available_timezones())


def _check_timezone(value: str) -> str:
    if value not in _TIMEZONES:
        raise ValueError("must be a valid IANA timezone, e.g. 'Asia/Bangkok'")
    return value


Timezone = Annotated[str, Field(max_length=64), AfterValidator(_check_timezone)]
DisplayName = Annotated[str, Field(min_length=1, max_length=100)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    locale: Locale
    timezone: str
    theme: Theme
    plan_tier: Literal["free", "pro"]
    is_mentor: bool


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: DisplayName | None = None
    locale: Locale | None = None
    timezone: Timezone | None = None
    theme: Theme | None = None


class SessionOut(BaseModel):
    """One signed-in device = one refresh-token family."""

    id: uuid.UUID
    user_agent: str | None
    ip: str | None
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime
    current: bool
