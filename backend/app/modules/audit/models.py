"""audit_logs (spec §2.9, NFR Auditability).

One row per change to an important entity, with the full before/after state.
`user_id` is the owner of the data (who sees it in their audit log), `actor_id`
who made the change (the trader now; a mentor in Phase 8). `account_id` scopes
rows to a trading account for the Accounts > Audit log tab.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models_base import Base

ACTIONS = ("create", "update", "archive", "unarchive", "delete")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
        Index("ix_audit_logs_account_created", "account_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # No FK: the log must outlive the account it describes.
    account_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(20))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID]
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
