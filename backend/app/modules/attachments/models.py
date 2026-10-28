"""attachments — uploaded images (playbook examples now; review/OCR images later)."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base


class Attachment(Base):
    __tablename__ = "attachments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    storage_key: Mapped[str] = mapped_column(String(200), unique=True)
    content_type: Mapped[str] = mapped_column(String(50))
    size_bytes: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str | None] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
