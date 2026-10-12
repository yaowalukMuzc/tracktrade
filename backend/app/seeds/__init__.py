"""Idempotent reference-data seeding: `python -m app.seeds`.

Rows are upserted by natural key (symbol code, system emotion-tag code,
mistake-category code), so running it repeatedly is safe and updates labels/specs.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.diagnosis.models import MistakeCategory
from app.modules.emotions.models import EmotionTag
from app.modules.symbols.models import Symbol

SEED_DIR = Path(__file__).parent


def load_yaml(name: str) -> list[dict[str, Any]]:
    with (SEED_DIR / f"{name}.yaml").open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    rows: list[dict[str, Any]] = data[name]
    return rows


async def seed_symbols(session: AsyncSession) -> int:
    rows = load_yaml("symbols")
    for row in rows:
        for key in ("point_size", "pip_size", "contract_size"):
            row[key] = Decimal(str(row[key]))
    stmt = insert(Symbol).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Symbol.code],
        set_={c: stmt.excluded[c] for c in rows[0] if c != "code"} | {"updated_at": text("now()")},
    )
    await session.execute(stmt)
    return len(rows)


async def seed_emotion_tags(session: AsyncSession) -> int:
    rows = load_yaml("emotion_tags")
    stmt = insert(EmotionTag).values([{**r, "user_id": None} for r in rows])
    stmt = stmt.on_conflict_do_update(
        # Matches the partial unique index uq_emotion_tags_system_code.
        index_elements=[EmotionTag.code],
        index_where=text("user_id IS NULL"),
        set_={c: stmt.excluded[c] for c in ("label_th", "label_en", "valence")}
        | {"updated_at": text("now()")},
    )
    await session.execute(stmt)
    return len(rows)


async def seed_mistake_categories(session: AsyncSession) -> int:
    rows = load_yaml("mistake_categories")
    stmt = insert(MistakeCategory).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[MistakeCategory.code],
        set_={c: stmt.excluded[c] for c in ("dimension", "label_th", "label_en")}
        | {"updated_at": text("now()")},
    )
    await session.execute(stmt)
    return len(rows)


async def run_seeds(session: AsyncSession) -> dict[str, int]:
    """Upsert all reference data in the caller's transaction."""
    return {
        "symbols": await seed_symbols(session),
        "emotion_tags": await seed_emotion_tags(session),
        "mistake_categories": await seed_mistake_categories(session),
    }
