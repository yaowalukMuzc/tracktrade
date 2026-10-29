"""Async SQLAlchemy engine + per-request session (unit of work).

Side effects that other processes observe — WebSocket events, background jobs — must only
happen once the data is committed, or a client could refetch and see the old state. Services
register them with `after_commit(session, fn)`; `get_session` (HTTP) and `commit_and_flush_hooks`
(worker / ingest) run them after a successful commit and drop them on rollback.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = structlog.get_logger(__name__)

AfterCommit = Callable[[], Awaitable[object]]
_HOOKS_KEY = "after_commit"


def create_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True)


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def after_commit(session: AsyncSession, fn: AfterCommit) -> None:
    """Run `fn()` after this session's transaction commits (never if it rolls back)."""
    session.info.setdefault(_HOOKS_KEY, []).append(fn)


async def run_after_commit_hooks(session: AsyncSession) -> None:
    hooks: list[AfterCommit] = session.info.pop(_HOOKS_KEY, [])
    for fn in hooks:
        try:
            await fn()
        except Exception:  # a failed notification must not fail the request
            log.exception("after_commit_hook_failed")


def discard_after_commit_hooks(session: AsyncSession) -> None:
    session.info.pop(_HOOKS_KEY, None)


async def commit_and_flush_hooks(session: AsyncSession) -> None:
    await session.commit()
    await run_after_commit_hooks(session)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, committed on success."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            discard_after_commit_hooks(session)
            await session.rollback()
            raise
        await run_after_commit_hooks(session)
