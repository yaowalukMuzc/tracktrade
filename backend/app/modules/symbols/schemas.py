from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict


class SymbolOut(BaseModel):
    """Prices/sizes are Decimals -> serialised as JSON strings (no float drift)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    asset_class: Literal["fx", "metal"]
    digits: int
    point_size: Decimal
    pip_size: Decimal
    contract_size: Decimal
    base_currency: str
    quote_currency: str
