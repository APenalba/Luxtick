"""Database session management for async SQLAlchemy."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings

# Main engine (full read-write access)
engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_size=5,
    max_overflow=10,
)

# Read-only engine for analytics/text-to-SQL queries
readonly_engine = create_async_engine(
    settings.database_url_readonly,
    echo=settings.log_level == "DEBUG",
    pool_size=3,
    max_overflow=5,
)

# Session factories
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
readonly_session = async_sessionmaker(
    readonly_engine, class_=AsyncSession, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-write database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_readonly_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a read-only database session for analytics queries."""
    async with readonly_session() as session:
        yield session


async def close_engines() -> None:
    """Dispose of all database engines (call on shutdown)."""
    await engine.dispose()
    await readonly_engine.dispose()
