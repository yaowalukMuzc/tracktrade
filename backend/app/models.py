"""Import every model so `Base.metadata` is complete (Alembic, tests)."""

from app.core.models_base import Base
from app.modules.accounts.models import (
    AccountSymbolOverride,
    RiskProfile,
    RiskProfileVersion,
    TradingAccount,
    TradingRule,
)
from app.modules.attachments.models import Attachment
from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthAccount, AuthJwk, AuthSession, AuthVerification
from app.modules.diagnosis.models import MistakeCategory
from app.modules.emotions.models import EmotionTag
from app.modules.playbook.models import Setup, SetupChecklistItem, SetupExample
from app.modules.symbols.models import Symbol
from app.modules.users.models import User

__all__ = [
    "AccountSymbolOverride",
    "Attachment",
    "AuditLog",
    "AuthAccount",
    "AuthJwk",
    "AuthSession",
    "AuthVerification",
    "Base",
    "EmotionTag",
    "MistakeCategory",
    "RiskProfile",
    "RiskProfileVersion",
    "Setup",
    "SetupChecklistItem",
    "SetupExample",
    "Symbol",
    "TradingAccount",
    "TradingRule",
    "User",
]
