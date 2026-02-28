"""
app/services/git_service.py
────────────────────────────
All git operations for a project workspace.
Runs git as a subprocess — no libgit2 dependency needed.

Security: the GitHub token is embedded in the remote URL only at push
time and is never logged or stored in the git config.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _git(args: list[str], cwd: str, env: dict | None = None) -> tuple[str, str, int]:
    """Run a git command, return (stdout, stderr, returncode)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, **(env or {})},
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(errors="replace"), stderr.decode(errors="replace"), proc.returncode or 0


async def _git_out(args: list[str], cwd: str, env: dict | None = None) -> str:
    """Run git and return stdout; raises RuntimeError on non-zero exit."""
    out, err, code = await _git(args, cwd, env)
    if code != 0:
        raise RuntimeError(err.strip() or f"git {args[0]} failed (exit {code})")
    return out.strip()


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class FileStatus:
    path: str
    status: str          # 'M' modified, 'A' added, 'D' deleted, '?' untracked, 'R' renamed
    label: str           # human-readable label


@dataclass
class CommitInfo:
    hash: str
    short_hash: str
    message: str
    author: str
    date: str


@dataclass
class GitStatus:
    branch: str
    ahead: int
    behind: int
    has_remote: bool
    files: list[FileStatus]
    is_clean: bool


# ── Service functions ─────────────────────────────────────────────────────────

async def ensure_repo(workdir: str) -> None:
    """Initialise a git repo in *workdir* if one doesn't already exist."""
    git_dir = Path(workdir) / ".git"
    if git_dir.is_dir():
        return

    await _git_out(["init", "--initial-branch=main"], workdir)
    await _git_out(["config", "user.email", "ai@basivo.dev"], workdir)
    await _git_out(["config", "user.name", "Basivo AI"], workdir)

    # Create a sensible default .gitignore
    gitignore = Path(workdir) / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "node_modules/\ndist/\nbuild/\n.next/\n"
            "__pycache__/\n*.pyc\n.env\n.env.*\n"
            "*.log\n.DS_Store\n.venv/\n"
        )


async def get_status(workdir: str) -> GitStatus:
    """Return the full repo status: branch, ahead/behind, changed files."""
    await ensure_repo(workdir)

    # Branch name
    try:
        branch = await _git_out(["rev-parse", "--abbrev-ref", "HEAD"], workdir)
    except RuntimeError:
        branch = "main"

    # Ahead / behind
    ahead = behind = 0
    has_remote = False
    try:
        tracking = await _git_out(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], workdir)
        if tracking:
            has_remote = True
            counts, _, code = await _git(["rev-list", "--left-right", "--count", "HEAD...@{u}"], workdir)
            if code == 0:
                parts = counts.strip().split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])
    except RuntimeError:
        pass

    # Changed files (porcelain v1)
    raw, _, _ = await _git(["status", "--porcelain", "-u"], workdir)
    files: list[FileStatus] = []

    STATUS_LABELS = {
        "M": "Modified", "A": "Added", "D": "Deleted",
        "R": "Renamed", "C": "Copied", "U": "Conflict",
        "?": "Untracked",
    }

    for line in raw.splitlines():
        if not line.strip():
            continue
        xy = line[:2]
        path = line[3:].strip().strip('"')
        # Use index status, fall back to working-tree status
        code = xy[0].strip() or xy[1].strip()
        if code == "?":
            code = "?"
        files.append(FileStatus(
            path=path,
            status=code,
            label=STATUS_LABELS.get(code, code),
        ))

    return GitStatus(
        branch=branch,
        ahead=ahead,
        behind=behind,
        has_remote=has_remote,
        files=files,
        is_clean=len(files) == 0,
    )


async def get_diff(workdir: str, path: Optional[str] = None) -> str:
    """
    Return unified diff text.
    - If *path* given: diff that single file
    - Otherwise: full diff of all staged+unstaged changes
    """
    await ensure_repo(workdir)

    args = ["diff", "HEAD", "--"]
    if path:
        args.append(path)

    diff, _, _ = await _git(args, workdir)
    if not diff:
        # Try diff of untracked file by showing its content
        if path:
            full = Path(workdir) / path
            if full.is_file():
                try:
                    content = full.read_text(errors="replace")
                    lines = [f"+{l}" for l in content.splitlines()]
                    diff = f"--- /dev/null\n+++ b/{path}\n@@ -0,0 +1,{len(lines)} @@\n" + "\n".join(lines)
                except OSError:
                    pass
    return diff


async def commit(workdir: str, message: str) -> dict:
    """Stage everything and create a commit. Returns commit info."""
    await ensure_repo(workdir)

    # Stage all changes
    await _git_out(["add", "-A"], workdir)

    # Commit
    try:
        out = await _git_out(["commit", "-m", message], workdir)
    except RuntimeError as exc:
        if "nothing to commit" in str(exc):
            return {"success": False, "message": "Nothing to commit — working tree is clean."}
        raise

    # Get the new commit hash
    short_hash = (await _git_out(["rev-parse", "--short", "HEAD"], workdir))
    return {"success": True, "hash": short_hash, "message": out}


async def push(workdir: str, repo_url: str, token: str, branch: str = "main") -> dict:
    """
    Push to a GitHub repo using a Personal Access Token.
    The token is embedded in the remote URL — never stored in git config.
    """
    await ensure_repo(workdir)

    # Embed token: https://token@github.com/user/repo.git
    auth_url = _inject_token(repo_url, token)

    # Set/update the remote temporarily
    _, _, code = await _git(["remote", "get-url", "origin"], workdir)
    if code == 0:
        await _git_out(["remote", "set-url", "origin", auth_url], workdir)
    else:
        await _git_out(["remote", "add", "origin", auth_url], workdir)

    # Push
    try:
        out = await _git_out(
            ["push", "-u", "origin", branch],
            workdir,
            env={"GIT_TERMINAL_PROMPT": "0"},  # never prompt for password
        )
        # Strip the token from any output before returning
        out = _redact_token(out, token)
        return {"success": True, "message": out or "Push successful"}
    except RuntimeError as exc:
        msg = _redact_token(str(exc), token)
        return {"success": False, "message": msg}
    finally:
        # Reset remote to clean URL (without token)
        clean_url = _clean_url(repo_url)
        await _git(["remote", "set-url", "origin", clean_url], workdir)


async def get_log(workdir: str, limit: int = 30) -> list[CommitInfo]:
    """Return the recent commit history."""
    await ensure_repo(workdir)
    SEP = "|||"
    fmt = f"%H{SEP}%h{SEP}%s{SEP}%an{SEP}%ar"
    try:
        out = await _git_out(["log", f"-{limit}", f"--pretty=format:{fmt}"], workdir)
    except RuntimeError:
        return []

    commits = []
    for line in out.splitlines():
        parts = line.split(SEP, 4)
        if len(parts) == 5:
            commits.append(CommitInfo(
                hash=parts[0], short_hash=parts[1],
                message=parts[2], author=parts[3], date=parts[4],
            ))
    return commits


def create_zip(workdir: str) -> bytes:
    """
    Create an in-memory ZIP archive of the workspace.
    Excludes node_modules, .git, __pycache__, dist, build directories.
    """
    SKIP_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", ".venv"}
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        base = Path(workdir)
        project_name = base.name

        for item in base.rglob("*"):
            # Skip excluded directories
            if any(part in SKIP_DIRS for part in item.relative_to(base).parts):
                continue
            if item.is_file():
                arcname = f"{project_name}/{item.relative_to(base)}"
                zf.write(item, arcname)

    return buf.getvalue()


# ── Private helpers ───────────────────────────────────────────────────────────

def _inject_token(url: str, token: str) -> str:
    """https://github.com/u/r.git → https://TOKEN@github.com/u/r.git"""
    url = url.strip()
    if url.startswith("https://"):
        return url.replace("https://", f"https://{token}@", 1)
    return url  # SSH URLs don't need token injection


def _clean_url(url: str) -> str:
    """Remove any embedded credentials from a URL."""
    return re.sub(r"(https://)([^@]+@)", r"\1", url)


def _redact_token(text: str, token: str) -> str:
    """Replace the token in any output string to prevent accidental logging."""
    if token and token in text:
        return text.replace(token, "***")
    return text
