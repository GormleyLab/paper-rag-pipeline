"""
Async SQLAlchemy database configuration for PostgreSQL with pgvector.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from src.core.settings import get_settings

logger = logging.getLogger(__name__)

# Global engine instance (initialized lazily)
_engine = None
_async_session_maker = None


def get_engine():
    """Get or create the async SQLAlchemy engine."""
    global _engine

    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            poolclass=NullPool,  # Better for serverless/async contexts
        )
        logger.info(f"Database engine created for {settings.database_url.split('@')[-1]}")

    return _engine


def get_session_maker():
    """Get or create the async session maker."""
    global _async_session_maker

    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _async_session_maker


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(query)
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """
    Initialize the database schema.
    Creates the paper_rag schema and enables pgvector extension.
    """
    from sqlalchemy import text

    engine = get_engine()

    async with engine.begin() as conn:
        # Create schema if not exists
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS paper_rag"))

        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        logger.info("Database initialized: schema and pgvector extension created")


async def close_db():
    """Close database connections."""
    global _engine, _async_session_maker

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database connections closed")
