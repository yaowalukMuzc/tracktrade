"""Import every model so `Base.metadata` is complete (Alembic, tests)."""

from app.core.models_base import Base
from app.modules.auth.models import RefreshToken
from app.modules.diagnosis.models import MistakeCategory
from app.modules.emotions.models import EmotionTag
from app.modules.symbols.models import Symbol
from app.modules.users.models import User

__all__ = ["Base", "EmotionTag", "MistakeCategory", "RefreshToken", "Symbol", "User"]
