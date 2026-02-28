"""
app/schemas/project.py
──────────────────────
Pydantic v2 request / response schemas for the Project domain.

Security rule: the raw `llm_api_key` is accepted on CREATE and never
returned in any response.  Clients see only a masked indicator.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


# ── Create ────────────────────────────────────────────────────────────────────

class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    # BYOK credentials
    llm_base_url: AnyHttpUrl = Field(
        description="OpenAI-compatible API base URL, e.g. https://api.openai.com/v1"
    )
    llm_api_key: str = Field(
        min_length=1,
        description="Your LLM provider API key — stored encrypted, never returned.",
    )
    llm_model: str | None = Field(
        default=None,
        max_length=128,
        description="Model identifier, e.g. 'gpt-4o'. Optional — OpenCode may auto-detect.",
    )


# ── Response ──────────────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    """
    Safe project representation — never exposes the raw API key.
    `api_key_set` is a boolean indicator so the frontend can show a
    "key configured ✓" badge without needing to reveal the value.
    """
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    llm_base_url: str
    llm_model: str | None
    api_key_set: bool = True   # always True if a project row exists
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, project: object) -> "ProjectResponse":
        """Build response from the ORM Project, explicitly masking the key."""
        from app.models.project import Project as ProjectModel  # local import avoids circulars
        assert isinstance(project, ProjectModel)
        return cls(
            id=project.id,
            owner_id=project.owner_id,
            name=project.name,
            description=project.description,
            llm_base_url=str(project.llm_base_url),
            llm_model=project.llm_model,
            api_key_set=bool(project.llm_api_key_encrypted),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int


# ── WebSocket message types ───────────────────────────────────────────────────

class WsIncomingMessage(BaseModel):
    """Shape of JSON messages sent FROM the React frontend over the WebSocket."""
    type: str = Field(description="Message type. Currently only 'prompt' is supported.")
    content: str = Field(description="The user prompt to pass to OpenCode.")


class WsOutgoingMessage(BaseModel):
    """
    Shape of JSON messages sent FROM the backend TO the React frontend.

    type values:
      'connected'  — handshake confirmation after WS auth
      'output'     — a chunk of stdout/stderr from OpenCode
      'complete'   — process finished (includes exit_code)
      'error'      — backend-level error (e.g. process couldn't start)
      'status'     — process status update (e.g. 'running', 'idle')
    """
    type: str
    data: str | None = None
    stream: str | None = None   # 'stdout' | 'stderr'
    exit_code: int | None = None
    message: str | None = None
