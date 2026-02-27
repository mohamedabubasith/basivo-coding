"""
app/models/project.py
─────────────────────
SQLAlchemy ORM model for the `projects` table.

Security notes:
  - `llm_api_key_encrypted` stores the user's OpenAI-compatible API key
    encrypted with Fernet symmetric encryption (see app/core/security.py).
    The plaintext key is NEVER written to the database.
  - `llm_base_url` is stored in plaintext (it is not a secret).

Docker workspace note:
  Each project is associated with a filesystem directory:
      {settings.projects_root}/{project.id}/
  This directory is where OpenCode reads and writes files.
  DOCKER MOUNT:  bind-mount `settings.projects_root` as a volume
  so the OpenCode container can access the project files:
      docker run -v /host/projects:/app/projects <opencode-image>
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    # ── Primary key ───────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # ── Ownership ─────────────────────────────────────────────────────────────
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Project metadata ──────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── LLM credentials (BYOK) ────────────────────────────────────────────────
    # OpenAI-compatible base URL, e.g. "https://api.openai.com/v1" or any
    # compatible provider (Together, Groq, local Ollama, etc.)
    llm_base_url: Mapped[str] = mapped_column(String(2048), nullable=False)

    # The API key encrypted with Fernet.  Use security.decrypt_value() to read.
    llm_api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Optional: the model identifier to pass to OpenCode, e.g. "gpt-4o"
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    owner: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        back_populates="projects",
        lazy="select",
    )

    @property
    def workspace_dir_name(self) -> str:
        """Directory name inside projects_root for this project."""
        return str(self.id)

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r} owner={self.owner_id}>"
