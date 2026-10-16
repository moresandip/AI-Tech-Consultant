"""Async PostgreSQL engine + session factory for Task 1."""

from __future__ import annotations

import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.settings import settings
from app.models import Base

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create all tables if they don't exist (idempotent with SQLite fallback in local dev)."""
    global engine, AsyncSessionLocal
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("PostgreSQL not reachable (%s); falling back to local SQLite dev db.", exc)
        engine = create_async_engine("sqlite+aiosqlite:///./knowledge_brain.db", echo=False)
        AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Local SQLite database initialized.")


async def get_session() -> AsyncSession:  # type: ignore[override]
    """FastAPI dependency that yields a session and auto-commits or rolls back."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
