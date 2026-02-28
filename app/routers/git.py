"""
app/routers/git.py
───────────────────
Git operations for a project workspace.

Routes
──────
GET    /api/v1/projects/{id}/git/status          → repo status + changed files
GET    /api/v1/projects/{id}/git/diff?path=      → unified diff (all or single file)
GET    /api/v1/projects/{id}/git/log             → commit history
POST   /api/v1/projects/{id}/git/commit          → stage all + commit
POST   /api/v1/projects/{id}/git/push            → push to GitHub remote
PATCH  /api/v1/projects/{id}/github              → update GitHub repo URL + token
GET    /api/v1/projects/{id}/download            → download workspace as ZIP
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.security import decrypt_value, encrypt_value
from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.project import GitHubSettingsRequest, ProjectResponse
from app.services import git_service
from app.services.project_service import _fetch_and_authorize
import os

router = APIRouter(tags=["Git"])


def _workspace(project_id: uuid.UUID) -> str:
    settings = get_settings()
    path = os.path.join(settings.projects_root, str(project_id))
    os.makedirs(path, exist_ok=True)
    return path


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/git/status", summary="Git repo status")
async def git_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    status = await git_service.get_status(_workspace(project_id))
    return {
        "branch": status.branch,
        "ahead": status.ahead,
        "behind": status.behind,
        "has_remote": status.has_remote,
        "is_clean": status.is_clean,
        "files": [
            {"path": f.path, "status": f.status, "label": f.label}
            for f in status.files
        ],
    }


# ── Diff ──────────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/git/diff", summary="Get unified diff")
async def git_diff(
    project_id: uuid.UUID,
    path: Optional[str] = Query(None, description="File path to diff; omit for full diff"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    diff = await git_service.get_diff(_workspace(project_id), path)
    return {"diff": diff, "path": path}


# ── Commit log ────────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/git/log", summary="Commit history")
async def git_log(
    project_id: uuid.UUID,
    limit: int = Query(30, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    commits = await git_service.get_log(_workspace(project_id), limit)
    return {
        "commits": [
            {
                "hash": c.hash,
                "short_hash": c.short_hash,
                "message": c.message,
                "author": c.author,
                "date": c.date,
            }
            for c in commits
        ]
    }


# ── Commit ────────────────────────────────────────────────────────────────────

class CommitRequest(BaseModel):
    message: str


@router.post("/projects/{project_id}/git/commit", summary="Stage all changes and commit")
async def git_commit(
    project_id: uuid.UUID,
    body: CommitRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _fetch_and_authorize(project_id, current_user, db)
    if not body.message.strip():
        return {"success": False, "message": "Commit message cannot be empty."}
    result = await git_service.commit(_workspace(project_id), body.message.strip())
    return result


# ── Push ──────────────────────────────────────────────────────────────────────

class PushRequest(BaseModel):
    branch: str = "main"


@router.post("/projects/{project_id}/git/push", summary="Push to GitHub remote")
async def git_push(
    project_id: uuid.UUID,
    body: PushRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project = await _fetch_and_authorize(project_id, current_user, db)

    if not project.github_repo_url:
        return {"success": False, "message": "No GitHub repo URL configured. Set it in project settings."}
    if not project.github_token_encrypted:
        return {"success": False, "message": "No GitHub token configured. Set it in project settings."}

    token = decrypt_value(project.github_token_encrypted)
    result = await git_service.push(
        _workspace(project_id),
        project.github_repo_url,
        token,
        body.branch,
    )
    return result


# ── Update GitHub settings ────────────────────────────────────────────────────

@router.patch(
    "/projects/{project_id}/github",
    response_model=ProjectResponse,
    summary="Update GitHub repo URL and/or token",
)
async def update_github_settings(
    project_id: uuid.UUID,
    body: GitHubSettingsRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await _fetch_and_authorize(project_id, current_user, db)

    if body.github_repo_url is not None:
        project.github_repo_url = body.github_repo_url or None
    if body.github_token is not None:
        project.github_token_encrypted = (
            encrypt_value(body.github_token) if body.github_token else None
        )

    await db.flush()
    await db.refresh(project)
    return ProjectResponse.from_orm_model(project)


# ── Download as ZIP ───────────────────────────────────────────────────────────

@router.get(
    "/projects/{project_id}/download",
    summary="Download the workspace as a ZIP file",
    response_class=Response,
)
async def download_zip(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    project = await _fetch_and_authorize(project_id, current_user, db)
    workdir = _workspace(project_id)

    zip_bytes = git_service.create_zip(workdir)
    filename = f"{project.name.replace(' ', '_')}.zip"

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
