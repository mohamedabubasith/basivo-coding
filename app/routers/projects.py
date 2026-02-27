"""
app/routers/projects.py
───────────────────────
REST endpoints for the Project Management domain.

Route summary
─────────────
GET    /api/v1/projects              → list current user's projects
POST   /api/v1/projects              → create a project (store encrypted API key)
GET    /api/v1/projects/{project_id} → get a single project
DELETE /api/v1/projects/{project_id} → delete a project
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectListResponse,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "",
    response_model=ProjectListResponse,
    summary="List all projects for the current user",
)
async def list_projects(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    """Return all projects owned by the authenticated user, newest first."""
    return await project_service.list_projects(current_user, db)


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project with BYOK credentials",
)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Create a project and securely store the user's LLM API key.

    The `llm_api_key` field is encrypted with Fernet before being written
    to the database.  It is never returned in any response — only a boolean
    `api_key_set` indicator is surfaced to the frontend.
    """
    return await project_service.create_project(payload, current_user, db)


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get a single project by ID",
)
async def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """
    Retrieve a project by its UUID.
    Returns 404 if the project does not exist OR belongs to another user.
    """
    return await project_service.get_project(project_id, current_user, db)


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a project and its database record.

    Note: the workspace directory on disk is not removed immediately.
    A background cleanup job should periodically purge orphaned directories.
    """
    await project_service.delete_project(project_id, current_user, db)
