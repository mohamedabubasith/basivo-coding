"""
app/services/project_service.py
────────────────────────────────
Business logic for Project CRUD.

Key responsibilities:
  - Encrypt the user-supplied API key before writing to DB.
  - Never expose the raw or encrypted key in return values.
  - Enforce ownership checks (a user may only touch their own projects).
"""

from __future__ import annotations

import os
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import encrypt_value
from app.models.project import Project
from app.models.user import User
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
)


def _ensure_workspace_dir(project_id: uuid.UUID) -> str:
    """
    Create the per-project workspace directory if it does not exist.

    Returns the absolute path to the directory.

    DOCKER MOUNT NOTE:
      The parent `projects_root` directory should be bind-mounted into the
      OpenCode container so the subprocess can read and write project files:

        # docker-compose.yml
        services:
          opencode-runner:
            image: opencode:latest
            volumes:
              - ${PROJECTS_ROOT:-./projects}:/app/projects
    """
    settings = get_settings()
    workspace = os.path.join(settings.projects_root, str(project_id))
    os.makedirs(workspace, exist_ok=True)
    return workspace


async def create_project(
    payload: ProjectCreateRequest,
    owner: User,
    db: AsyncSession,
) -> ProjectResponse:
    """
    Persist a new project with an encrypted API key.

    The plaintext `llm_api_key` from the request is encrypted immediately
    and only the ciphertext reaches the database row.
    """
    encrypted_key = encrypt_value(payload.llm_api_key)

    project = Project(
        owner_id=owner.id,
        name=payload.name,
        description=payload.description,
        llm_base_url=str(payload.llm_base_url),
        llm_api_key_encrypted=encrypted_key,
        llm_model=payload.llm_model,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    # Materialise the workspace directory so OpenCode has a place to work.
    _ensure_workspace_dir(project.id)

    return ProjectResponse.from_orm_model(project)


async def list_projects(owner: User, db: AsyncSession) -> ProjectListResponse:
    """Return all projects owned by *owner*, ordered by creation time descending."""
    result = await db.execute(
        select(Project)
        .where(Project.owner_id == owner.id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[ProjectResponse.from_orm_model(p) for p in projects],
        total=len(projects),
    )


async def get_project(
    project_id: uuid.UUID,
    owner: User,
    db: AsyncSession,
) -> ProjectResponse:
    """
    Retrieve a single project by ID.

    Raises:
        NotFoundError:  project does not exist.
        ForbiddenError: project belongs to another user.
    """
    project = await _fetch_and_authorize(project_id, owner, db)
    return ProjectResponse.from_orm_model(project)


async def delete_project(
    project_id: uuid.UUID,
    owner: User,
    db: AsyncSession,
) -> None:
    """
    Delete a project row.  The workspace directory is intentionally NOT
    removed here to avoid accidental data loss; a separate cleanup job
    should handle orphaned directories.
    """
    project = await _fetch_and_authorize(project_id, owner, db)
    await db.delete(project)
    await db.flush()


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _fetch_and_authorize(
    project_id: uuid.UUID,
    owner: User,
    db: AsyncSession,
) -> Project:
    """Fetch project by ID and verify ownership. Raises on failure."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project is None:
        raise NotFoundError("Project")

    if project.owner_id != owner.id:
        # Return 404 instead of 403 to avoid confirming the project exists
        raise NotFoundError("Project")

    return project


async def get_project_for_workspace(
    project_id: uuid.UUID,
    owner: User,
    db: AsyncSession,
) -> Project:
    """
    Like `_fetch_and_authorize` but returns the full ORM object
    (including encrypted key) for internal service use by opencode_service.
    """
    return await _fetch_and_authorize(project_id, owner, db)
