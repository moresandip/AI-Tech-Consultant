"""Async PostgreSQL engine for Task 3."""

from __future__ import annotations

import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

try:
    from app.models import Base
except ImportError:
    from models import Base

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tech_consultant"
)

engine = create_async_engine(DATABASE_URL, pool_size=10, max_overflow=20, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables if they don't exist (with fallback to SQLite in local dev)."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("PostgreSQL not reachable (%s); falling back to local SQLite dev db.", exc)
        engine = create_async_engine("sqlite+aiosqlite:///./meeting_scope.db", echo=False)
        AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database for Meeting Scope initialized.")


async def get_session() -> AsyncSession:  # type: ignore[override]
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
