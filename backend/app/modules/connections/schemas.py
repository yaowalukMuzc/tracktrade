"""Ingest payload (connectors/mt5-ea/PROTOCOL.md v1) and connection API shapes.

The cTrader worker maps its own messages onto the same `IngestIn`, so both brokers share one
idempotent pipeline (`connections.ingest`).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _decimal_text(value: object) -> object:
    """Numbers travel as strings (no float rounding). Ints are fine; floats are refused."""
    if isinstance(value, bool | float):
        raise ValueError('send numbers as strings, e.g. "4387.60"')
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except InvalidOperation as exc:
            raise ValueError(f"not a number: {value!r}") from exc
    return value


Num = Annotated[Decimal, BeforeValidator(_decimal_text)]
Ts = Annotated[int, Field(ge=946684800, le=4102444800)]  # 2000-01-01 .. 2100-01-01, UTC seconds
Id = Annotated[str, Field(min_length=1, max_length=64)]
SymbolName = Annotated[str, Field(min_length=1, max_length=32)]
Timeframe = Literal["M1", "M5", "M15", "M30", "H1", "H4", "D1"]


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AccountIn(_In):
    login: Annotated[str, Field(max_length=64)] = ""
    server: Annotated[str, Field(max_length=100)] = ""
    company: Annotated[str, Field(max_length=100)] = ""
    currency: Annotated[str, Field(max_length=3)] = ""
    balance: Num | None = None
    equity: Num | None = None
    margin_mode: Literal["hedging", "netting"] = "hedging"
    is_live: bool | None = None  # cTrader tells us; MT5 leaves it out


class SymbolIn(_In):
    name: SymbolName
    digits: Annotated[int, Field(ge=0, le=10)] | None = None
    point: Num | None = None
    contract_size: Num | None = None
    tick_size: Num | None = None
    tick_value: Num | None = None
    currency_base: str = ""
    currency_profit: str = ""


class DealIn(_In):
    ticket: Id
    order: Annotated[str, Field(max_length=64)] = ""
    position_id: Id
    symbol: SymbolName
    entry: Literal["in", "out", "inout", "out_by"]
    type: Literal["buy", "sell"]
    volume: Num
    price: Num
    time: Ts
    commission: Num = Decimal(0)
    swap: Num = Decimal(0)
    fee: Num = Decimal(0)
    profit: Num = Decimal(0)
    sl: Num = Decimal(0)
    tp: Num = Decimal(0)


class OpenPositionIn(_In):
    position_id: Id
    symbol: SymbolName
    type: Literal["buy", "sell"]
    volume: Num
    price_open: Num
    sl: Num = Decimal(0)
    tp: Num = Decimal(0)
    time: Ts | None = None


class ModificationIn(_In):
    id: Annotated[str, Field(min_length=1, max_length=96)]
    position_id: Id
    field: Literal["sl", "tp"]
    old: Num = Decimal(0)
    new: Num = Decimal(0)
    time: Ts


Bar = tuple[Ts, Num, Num, Num, Num, Num]


class OhlcIn(_In):
    symbol: SymbolName
    timeframe: Timeframe
    bars: Annotated[list[Bar], Field(max_length=20_000)]


class HistoryIn(_In):
    from_: Annotated[Ts, Field(alias="from")]
    to: Ts
    final: bool = False


class IngestIn(_In):
    ea_version: Annotated[str, Field(max_length=20)] = ""
    sent_at: Ts | None = None
    account: AccountIn
    symbols: Annotated[list[SymbolIn], Field(max_length=200)] = []
    deals: Annotated[list[DealIn], Field(max_length=500)] = []
    positions: Annotated[list[OpenPositionIn], Field(max_length=500)] = []
    modifications: Annotated[list[ModificationIn], Field(max_length=500)] = []
    ohlc: Annotated[list[OhlcIn], Field(max_length=100)] = []
    history: HistoryIn | None = None


class Counted(BaseModel):
    deals: int = 0
    modifications: int = 0
    bars: int = 0


class CommandOut(BaseModel):
    id: uuid.UUID
    kind: Literal["resync", "ohlc"]
    params: dict[str, Any]


class IngestOut(BaseModel):
    accepted: Counted
    duplicates: Counted
    unknown_symbols: list[str]
    server_time: int
    commands: list[CommandOut]


# ------------------------------------------------------------------ connections API

ConnectionStatus = Literal["pending", "connected", "offline", "error"]


class ConnectionStats(BaseModel):
    deals_today: int
    mods_today: int
    history_days: int | None  # how far back the first import reached


class ConnectionOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    kind: Literal["mt5_ea", "ctrader_oauth"]
    status: ConnectionStatus
    key_hint: str | None
    external_account_id: str | None
    server: str | None
    ea_version: str | None
    last_seen_at: datetime | None
    last_sync_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    history_synced_at: datetime | None
    stats: ConnectionStats
    created_at: datetime


class ApiKeyOut(BaseModel):
    """The only time the full key is returned."""

    connection: ConnectionOut
    api_key: str


class IngestionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    source: str
    status: str
    stats: dict[str, Any]
    error: str | None
    attempts: int
    started_at: datetime
    finished_at: datetime | None


class AuthorizeOut(BaseModel):
    authorize_url: str
