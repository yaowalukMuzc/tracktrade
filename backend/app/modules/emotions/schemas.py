from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class EmotionTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    label_th: str
    label_en: str
    valence: Literal["pos", "neg", "neutral"]
    is_system: bool
