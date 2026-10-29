"""Import every model so `Base.metadata` is complete (Alembic, tests)."""

from app.core.models_base import Base
from app.modules.accounts.models import (
    AccountSymbolOverride,
    RiskProfile,
    RiskProfileVersion,
    TradingAccount,
    TradingRule,
)
from app.modules.analysis.models import ChartDrawing, MarketAnalysis
from app.modules.attachments.models import Attachment
from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthAccount, AuthJwk, AuthSession, AuthVerification
from app.modules.connections.models import BrokerConnection, IngestCommand, IngestionJob
from app.modules.diagnosis.models import MistakeCategory
from app.modules.emotions.models import EmotionLog, EmotionTag
from app.modules.market_data.models import ohlc_bars
from app.modules.plans.models import PlanChecklistAnswer, TradePlan, TradePlanRevision
from app.modules.playbook.models import Setup, SetupChecklistItem, SetupExample
from app.modules.positions.models import Execution, OrderModification, Position
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
    "BrokerConnection",
    "ChartDrawing",
    "EmotionLog",
    "EmotionTag",
    "Execution",
    "IngestCommand",
    "IngestionJob",
    "MarketAnalysis",
    "MistakeCategory",
    "OrderModification",
    "PlanChecklistAnswer",
    "Position",
    "RiskProfile",
    "RiskProfileVersion",
    "Setup",
    "SetupChecklistItem",
    "SetupExample",
    "Symbol",
    "TradePlan",
    "TradePlanRevision",
    "TradingAccount",
    "TradingRule",
    "User",
    "ohlc_bars",
]
