"""Broker connections (MT5 EA key / cTrader OAuth), ingestion history, EA commands (F-08)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

KINDS = ("mt5_ea", "ctrader_oauth")
# pending = key created / OAuth done but no data yet; connected; error = last sync failed.
CONNECTION_STATUSES = ("pending", "connected", "error")
JOB_KINDS = ("sync", "history", "resync", "manual", "ocr")
JOB_SOURCES = ("mt5", "ctrader", "manual", "ocr")
JOB_STATUSES = ("running", "success", "warning", "error")
COMMAND_KINDS = ("resync", "ohlc")
COMMAND_STATUSES = ("pending", "delivered")


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        CheckConstraint(f"kind IN {KINDS}", name="kind"),
        CheckConstraint(f"status IN {CONNECTION_STATUSES}", name="status"),
        UniqueConstraint("account_id", "kind"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(14))
    status: Mapped[str] = mapped_column(String(10), default="pending")
    # MT5: sha256 of the API key (NFR: keys stored hashed) + a hint to recognise it (PLAN M13).
    api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str | None] = mapped_column(String(16))
    key_last4: Mapped[str | None] = mapped_column(String(4))
    # cTrader: Fernet-encrypted {"access_token", "refresh_token", "expires_at"} (NFR).
    oauth_tokens: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # MT5 login / cTrader ctidTraderAccountId, + server, company, EA version, is_live …
    external_account_id: Mapped[str | None] = mapped_column(String(64))
    external_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    history_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestionJob(Base):
    """One import: an EA batch with trades, a cTrader sync, a history import, a manual entry."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        CheckConstraint(f"kind IN {JOB_KINDS}", name="kind"),
        CheckConstraint(f"source IN {JOB_SOURCES}", name="source"),
        CheckConstraint(f"status IN {JOB_STATUSES}", name="status"),
        Index("ix_ingestion_jobs_account_created", "account_id", "created_at"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trading_accounts.id", ondelete="CASCADE")
    )
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="SET NULL")
    )
    kind: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(8), default="running")
    # {"deals", "positions", "modifications", "bars", "duplicates", "unknown_symbols": [...]}
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IngestCommand(Base):
    """Work for the EA, delivered in the response of its next heartbeat (PLAN M14)."""

    __tablename__ = "ingest_commands"
    __table_args__ = (
        CheckConstraint(f"kind IN {COMMAND_KINDS}", name="kind"),
        CheckConstraint(f"status IN {COMMAND_STATUSES}", name="status"),
        Index("ix_ingest_commands_pending", "connection_id", "status", "available_at"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("broker_connections.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(String(8))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="pending")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
