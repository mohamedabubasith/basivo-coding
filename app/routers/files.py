"""
app/routers/files.py
─────────────────────
File-system REST endpoints for a project's workspace.

Routes
──────
GET    /api/v1/projects/{id}/files              → full file tree (JSON)
GET    /api/v1/projects/{id}/files/content      → read one file (?path=src/App.tsx)
PUT    /api/v1/projects/{id}/files/content      → write/create a file
DELETE /api/v1/projects/{id}/files              → delete a file (?path=src/old.ts)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.services import file_service
from app.services.project_service import _fetch_and_authorize

router = APIRouter(tags=["Files"])


def _workspace(project_id: uuid.UUID) -> str:
    import os
    settings = get_settings()
    path = os.path.join(settings.projects_root, str(project_id))
    os.makedirs(path, exist_ok=True)
    return path


# ── File tree ─────────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/files",
    summary="Get the full file tree for a project workspace",
)
async def get_file_tree(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    return file_service.get_file_tree(_workspace(project_id))


# ── Read file ────────────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/files/content",
    summary="Read a single file's content",
)
async def read_file(
    project_id: uuid.UUID,
    path: str = Query(..., description="File path relative to the workspace root"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    content = file_service.read_file(_workspace(project_id), path)
    language = file_service._detect_language(path.split("/")[-1])
    return {"path": path, "content": content, "language": language}


# ── Write file ────────────────────────────────────────────────────────────────

class WriteFileRequest(BaseModel):
    path: str
    content: str


@router.put(
    "/projects/{project_id}/files/content",
    summary="Write (create or overwrite) a file",
)
async def write_file(
    project_id: uuid.UUID,
    body: WriteFileRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    file_service.write_file(_workspace(project_id), body.path, body.content)
    return {"path": body.path, "saved": True}


# ── Delete file ───────────────────────────────────────────────────────────────

@router.delete(
    "/projects/{project_id}/files",
    summary="Delete a file from the workspace",
)
async def delete_file(
    project_id: uuid.UUID,
    path: str = Query(..., description="File path relative to the workspace root"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    file_service.delete_file(_workspace(project_id), path)
    return {"path": path, "deleted": True}
