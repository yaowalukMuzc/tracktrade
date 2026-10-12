"""symbols reference table (spec §2.3, F-03)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base, Price

ASSET_CLASSES = ("fx", "metal")


class Symbol(Base):
    __tablename__ = "symbols"
    __table_args__ = (CheckConstraint(f"asset_class IN {ASSET_CLASSES}", name="asset_class"),)

    code: Mapped[str] = mapped_column(String(32), unique=True)
    asset_class: Mapped[str] = mapped_column(String(10))
    digits: Mapped[int] = mapped_column(Integer)
    point_size: Mapped[Price]
    pip_size: Mapped[Price]
    contract_size: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    base_currency: Mapped[str] = mapped_column(String(3))
    quote_currency: Mapped[str] = mapped_column(String(3))
