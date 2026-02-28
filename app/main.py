"""
app/main.py
───────────
FastAPI application factory with lifespan management.

Startup sequence:
  1. Initialise the async DB engine (init_db).
  2. Run create_tables() in dev mode (set CREATE_TABLES=true in .env).
     In production, use: alembic upgrade head
  3. Mount all routers under /api/v1.
  4. Register exception handlers.
  5. Configure CORS.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database import create_tables, init_db
from app.routers import auth, projects, workspace

# Basic config at import time; level is updated inside create_app() once settings load.
logging.basicConfig(format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    AsyncContextManager that runs startup logic before `yield` and
    teardown logic after (when the server shuts down).
    """
    settings = get_settings()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)

    # Initialise the SQLAlchemy async engine
    init_db()
    logger.info("Database engine initialised: %s", settings.database_url.split("@")[-1])

    # Dev convenience: auto-create tables without running Alembic.
    # Set CREATE_TABLES=true in .env for local development.
    # NEVER use this in production — always run `alembic upgrade head`.
    if os.environ.get("CREATE_TABLES", "false").lower() == "true":
        logger.warning(
            "CREATE_TABLES=true — creating tables via SQLAlchemy. "
            "Use `alembic upgrade head` in production."
        )
        await create_tables()

    # Ensure the projects root directory exists
    os.makedirs(settings.projects_root, exist_ok=True)
    logger.info("Projects root: %s", settings.projects_root)

    yield  # Server is running

    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    settings = get_settings()
    logging.getLogger().setLevel(logging.DEBUG if settings.debug else logging.INFO)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "BYOK (Bring Your Own Key) coding agent backend. "
            "Bridges the React workspace frontend with isolated OpenCode CLI instances."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception handlers ────────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routers ───────────────────────────────────────────────────────────────
    API_PREFIX = "/api/v1"

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(projects.router, prefix=API_PREFIX)
    # Workspace router mounts both the WS endpoint AND the REST status endpoint
    app.include_router(workspace.router, prefix=API_PREFIX)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["Health"], summary="Liveness probe")
    async def health() -> dict:
        return {"status": "ok", "version": settings.app_version}

    return app


# The ASGI app instance — used by uvicorn directly:
#   uvicorn app.main:app --reload
app = create_app()
