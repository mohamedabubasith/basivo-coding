"""
app/database.py
───────────────
Async SQLAlchemy 2.x engine + session factory.

Pattern used: dependency-injected AsyncSession per request.
The engine is created once at startup via the lifespan handler in main.py.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# Module-level singletons — populated by `init_db()` at startup.
_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db() -> None:
    """
    Create the async engine and session factory.
    Call once from the FastAPI lifespan handler so settings are resolved first.
    """
    global _engine, _async_session_factory

    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,      # log SQL in debug mode
        pool_pre_ping=True,       # discard stale connections
        pool_size=10,
        max_overflow=20,
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,   # avoid lazy-load issues after commit
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.

    Usage:
        @router.get("/")
        async def handler(db: AsyncSession = Depends(get_db)):
            ...
    """
    if _async_session_factory is None:
        raise RuntimeError("Database not initialised. Call init_db() first.")

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """
    Create all tables defined in the ORM models (dev/test convenience).
    In production, prefer Alembic migrations (`alembic upgrade head`).
    """
    # Import models here to ensure they are registered with Base.metadata
    from app.models import user, project  # noqa: F401

    if _engine is None:
        raise RuntimeError("Engine not initialised. Call init_db() first.")

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables — used in test teardown only."""
    from app.models import user, project  # noqa: F401

    if _engine is None:
        return

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
