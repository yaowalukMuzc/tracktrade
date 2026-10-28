"""Migration 0002 (Better Auth): Phase 1 users keep their password (F-01 AC8)."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
from tests.conftest import TEST_DATABASE_URL, alembic_config

# argon2-cffi hash of "correct-horse-1" (same fixture as auth/test/helpers.ts)
PHASE1_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$jEpJWGllzOBjiPHyDJfC9w$"
    "pX5lzuVhCYsoKwRRZQAjhZD5GR6OLXcnoSsfefAg9YE"
)


def _sql(statement: str, **params: Any) -> list[Any]:
    async def run() -> list[Any]:
        engine = create_async_engine(TEST_DATABASE_URL)
        try:
            async with engine.begin() as conn:
                result = await conn.execute(text(statement), params)
                return list(result.mappings()) if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_upgrade_moves_password_hashes_to_auth_accounts() -> None:
    cfg = alembic_config()
    command.downgrade(cfg, "0001")
    try:
        _sql(
            "INSERT INTO users (id, email, password_hash, display_name) "
            "VALUES (gen_random_uuid(), 'old@example.com', :h, 'Old')",
            h=PHASE1_HASH,
        )
        command.upgrade(cfg, "head")
        rows = _sql(
            "SELECT u.id::text AS uid, a.account_id, a.provider_id, a.password, u.email_verified "
            "FROM users u JOIN auth_accounts a ON a.user_id = u.id"
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["account_id"] == row["uid"]
        assert row["provider_id"] == "credential"
        assert row["password"] == PHASE1_HASH
        assert row["email_verified"] is False
        columns = _sql(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'"
        )
        assert "password_hash" not in {c["column_name"] for c in columns}
        assert not _sql("SELECT 1 FROM information_schema.tables WHERE table_name='refresh_tokens'")

        # And back down: the hash returns to users.password_hash.
        command.downgrade(cfg, "0001")
        assert _sql("SELECT password_hash FROM users")[0]["password_hash"] == PHASE1_HASH
    finally:
        command.upgrade(cfg, "head")
        _sql("DELETE FROM users")
