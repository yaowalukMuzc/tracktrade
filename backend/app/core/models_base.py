"""Declarative base shared by every table: uuid id + UTC timestamps."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import DateTime, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names so Alembic autogenerate produces stable diffs.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Column type aliases (spec §2: money numeric(18,2), price numeric(18,6)).
Money = Annotated[Decimal, mapped_column(Numeric(18, 2))]
Price = Annotated[Decimal, mapped_column(Numeric(18, 6))]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> uuid.UUID:
    """uuid7 when available (time-ordered, index friendly), else uuid4."""
    factory = getattr(uuid, "uuid7", None)
    if factory is not None:
        value: uuid.UUID = factory()
        return value
    return uuid.uuid4()


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow
    )
