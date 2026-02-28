"""
tests/conftest.py
─────────────────
Shared pytest fixtures.

All fixtures are function-scoped: each test gets a fresh in-memory
SQLite database.  This gives perfect isolation at the cost of slightly
more setup per test — entirely acceptable for an in-memory backend.

The `engine` and `db_session` share the same asyncio event loop
(function scope) so there is no cross-loop confusion with pytest-asyncio.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    """
    Yield a fresh async session backed by an in-memory SQLite DB.
    The DB is created and torn down per test — no state leaks between tests.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Register models with Base.metadata before creating tables
    from app.models import User, Project  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        bind=engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """
    Async test client with the `get_db` dependency overridden to use
    the per-test SQLite session — no real PostgreSQL required.
    """
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ── Convenience fixtures ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a test user and return the response JSON."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "Secret123"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict:
    """Return Authorization headers for the registered test user."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "test@example.com", "password": "Secret123"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
