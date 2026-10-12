from __future__ import annotations

import asyncio

import structlog

from app.core.config import get_settings
from app.core.db import create_engine, create_sessionmaker
from app.core.logging import configure_logging
from app.seeds import run_seeds


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)
    engine = create_engine(settings.DATABASE_URL)
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            counts = await run_seeds(session)
        structlog.get_logger("seeds").info("seeded", **counts)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
