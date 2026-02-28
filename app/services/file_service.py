"""
app/services/file_service.py
─────────────────────────────
File-system operations scoped to a project's workspace directory.

SECURITY: All paths are normalised and checked against the workspace root
to prevent directory-traversal attacks.  Any path that resolves outside the
workspace raises a 400 Bad Request.
"""
from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import HTTPException, status


def _safe_resolve(workspace_dir: str, user_path: str) -> Path:
    """
    Resolve *user_path* relative to *workspace_dir* and assert it stays inside.

    Raises HTTP 400 on traversal attempts.
    """
    base = Path(workspace_dir).resolve()
    # Strip leading slashes so Path join doesn't treat it as absolute
    clean = user_path.lstrip("/").lstrip("\\")
    full = (base / clean).resolve()

    if not str(full).startswith(str(base)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid path: directory traversal is not allowed.",
        )
    return full


def _file_node(path: Path, base: Path) -> dict:
    rel = path.relative_to(base)
    return {
        "name": path.name,
        "path": str(rel).replace("\\", "/"),
        "type": "file",
        "size": path.stat().st_size,
        "language": _detect_language(path.name),
    }


def _dir_node(path: Path, base: Path, depth: int = 0, max_depth: int = 10) -> dict:
    rel = path.relative_to(base)
    node: dict = {
        "name": path.name,
        "path": str(rel).replace("\\", "/") if rel.parts else "",
        "type": "directory",
        "children": [],
    }
    if depth >= max_depth:
        return node

    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return node

    for entry in entries:
        # Skip hidden files and common noise dirs in the top level
        if entry.name.startswith(".") and entry.name not in (".env.example",):
            continue
        if entry.name in ("node_modules", "__pycache__", ".git", "dist", ".next", "build"):
            continue
        if entry.is_dir():
            node["children"].append(_dir_node(entry, base, depth + 1, max_depth))
        elif entry.is_file():
            node["children"].append(_file_node(entry, base))

    return node


def get_file_tree(workspace_dir: str) -> dict:
    """Return the full file tree for the workspace."""
    base = Path(workspace_dir).resolve()
    if not base.exists():
        return {"name": "", "path": "", "type": "directory", "children": []}
    return _dir_node(base, base)


def read_file(workspace_dir: str, file_path: str) -> str:
    """Read and return a text file's contents."""
    full = _safe_resolve(workspace_dir, file_path)
    if not full.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not full.is_file():
        raise HTTPException(status_code=400, detail="Path is a directory, not a file.")

    # Guard against very large files (>2 MB)
    size = full.stat().st_size
    if size > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({size // 1024} KB). Maximum is 2 MB.",
        )

    try:
        return full.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not read file: {exc}")


def write_file(workspace_dir: str, file_path: str, content: str) -> None:
    """Write *content* to a file, creating parent directories as needed."""
    full = _safe_resolve(workspace_dir, file_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    try:
        full.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write file: {exc}")


def delete_file(workspace_dir: str, file_path: str) -> None:
    """Delete a single file (not directories)."""
    full = _safe_resolve(workspace_dir, file_path)
    if not full.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if full.is_dir():
        raise HTTPException(status_code=400, detail="Use a directory delete endpoint for directories.")
    try:
        full.unlink()
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not delete file: {exc}")


def _detect_language(filename: str) -> str:
    """Map filename extension to Monaco language identifier."""
    EXT_MAP = {
        ".ts": "typescript", ".tsx": "typescriptreact",
        ".js": "javascript", ".jsx": "javascriptreact",
        ".py": "python", ".rs": "rust", ".go": "go",
        ".java": "java", ".c": "c", ".cpp": "cpp", ".h": "c",
        ".cs": "csharp", ".php": "php", ".rb": "ruby",
        ".html": "html", ".htm": "html", ".css": "css",
        ".scss": "scss", ".sass": "sass", ".less": "less",
        ".json": "json", ".jsonc": "json",
        ".yaml": "yaml", ".yml": "yaml",
        ".toml": "toml", ".md": "markdown",
        ".sh": "shell", ".bash": "shell", ".zsh": "shell",
        ".sql": "sql", ".graphql": "graphql", ".gql": "graphql",
        ".xml": "xml", ".svg": "xml",
        ".env": "shell", ".gitignore": "shell",
        ".dockerfile": "dockerfile", "dockerfile": "dockerfile",
    }
    name_lower = filename.lower()
    # Check full filename first (for Dockerfile, .env, etc.)
    if name_lower in EXT_MAP:
        return EXT_MAP[name_lower]
    ext = os.path.splitext(name_lower)[1]
    return EXT_MAP.get(ext, "plaintext")
