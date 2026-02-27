"""
app/config.py
─────────────
All runtime configuration is read from environment variables via pydantic-settings.
A single `get_settings()` function (cached with lru_cache) acts as the DI source
so tests can easily override individual fields without touching os.environ.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Basivo BYOK Coding Agent"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────
    # asyncpg driver requires the postgresql+asyncpg:// scheme
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/basivo"

    # ── JWT ───────────────────────────────────────────────────────────────────
    # Generate a strong secret: python -c "import secrets; print(secrets.token_hex(32))"
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION_use_secrets_token_hex_32"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours

    # ── Encryption ────────────────────────────────────────────────────────────
    # Fernet key for encrypting API keys at rest.
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    encryption_key: str = "CHANGE_ME_IN_PRODUCTION_generate_fernet_key"

    # ── Password Reset (mocked) ───────────────────────────────────────────────
    reset_token_expire_minutes: int = 30

    # ── OpenCode CLI ──────────────────────────────────────────────────────────
    # Path to the opencode binary (or "opencode" if on PATH).
    opencode_binary: str = "opencode"
    # Root directory where per-project workspace folders are created.
    # DOCKER MOUNT POINT: bind-mount this path as a volume so the container
    # running OpenCode can read/write user project files.
    #   docker run -v /host/projects:/app/projects <image>
    projects_root: str = "/app/projects"
    # Hard timeout (seconds) for a single OpenCode subprocess invocation.
    opencode_timeout_seconds: int = 300

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance. Safe to call from anywhere."""
    return Settings()
