"""
alembic/env.py
──────────────
Alembic migration environment configured for async SQLAlchemy.

Key points:
  - Reads DATABASE_URL from the environment (or .env via pydantic-settings).
  - Imports all ORM models via `app.models` so autogenerate can detect changes.
  - Uses `run_sync` inside an async context for the actual migration run.

Usage:
  # Apply all pending migrations
  alembic upgrade head

  # Generate a new auto-detected migration
  alembic revision --autogenerate -m "add some_column to projects"

  # Downgrade one step
  alembic downgrade -1
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ── FastAPI app imports ───────────────────────────────────────────────────────
# Importing models ensures their metadata is registered with Base.
from app.config import get_settings
from app.database import Base
from app.models import User, Project  # noqa: F401 — register metadata

# ── Alembic config ────────────────────────────────────────────────────────────
alembic_cfg = context.config

# Interpret the config file for Python logging
if alembic_cfg.config_file_name is not None:
    fileConfig(alembic_cfg.config_file_name)

# The MetaData object from our ORM — alembic uses this for autogenerate
target_metadata = Base.metadata


def get_url() -> str:
    """Return the async database URL from application settings."""
    return get_settings().database_url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generate SQL without a live connection).
    Useful for reviewing migration SQL before applying it.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """Inner sync function called from the async runner."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,        # detect column type changes
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.
    We use `run_sync` to bridge the async engine with Alembic's sync API.
    """
    connectable = create_async_engine(get_url(), echo=False)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# ── Entry point ───────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
