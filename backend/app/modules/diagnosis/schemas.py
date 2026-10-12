from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict

Dimension = Literal["analysis", "planning", "execution", "risk", "discipline", "emotion"]


class MistakeCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    dimension: Dimension
    label_th: str
    label_en: str
