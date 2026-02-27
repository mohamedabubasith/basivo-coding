"""
app/services/opencode_service.py
─────────────────────────────────
The core engine: wraps the OpenCode CLI as an async subprocess and streams
its output to connected WebSocket clients in real time.

Architecture overview
─────────────────────

  React Frontend
       │  (WebSocket frames)
       ▼
  workspace.py router        ← receives user prompts, forwards to this service
       │
       ▼
  ConnectionManager          ← tracks active WebSocket + running process per project
       │
       ▼
  OpenCodeService.run_prompt()
       │
       ├── decrypt API key
       ├── build argv list (NO shell interpolation — safe from injection)
       ├── asyncio.create_subprocess_exec(...)
       │       workdir = {projects_root}/{project_id}/
       │
       ├── asyncio.gather(
       │       _stream_stdout(proc, ws, project_id),
       │       _stream_stderr(proc, ws, project_id),
       │   )
       │
       └── send WsOutgoingMessage(type='complete', exit_code=...)


OpenCode CLI assumptions
────────────────────────
OpenCode is invoked as:

    opencode run "<prompt>"

with LLM credentials supplied through environment variables:

    OPENAI_API_KEY    — the user's decrypted key
    OPENAI_BASE_URL   — the user's custom base URL
    OPENCODE_MODEL    — optional model override

This follows the de-facto convention used by OpenAI-compatible CLIs.
If your OpenCode binary uses different flags, adjust `_build_command()`.

DOCKER NOTE
───────────
When OpenCode runs inside a container the subprocess call is replaced with
a `docker run` invocation.  See the commented block in `_build_command()`.
The per-project workspace directory must be bind-mounted so OpenCode can
read and write user files:

    docker run --rm
      -e OPENAI_API_KEY=<key>
      -e OPENAI_BASE_URL=<url>
      -v /host/projects/<project_id>:/workspace
      opencode:latest run "<prompt>"
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from typing import TYPE_CHECKING

from fastapi import WebSocket

from app.config import get_settings
from app.core.exceptions import ProcessAlreadyRunningError, WorkspaceError
from app.core.security import decrypt_value
from app.schemas.project import WsOutgoingMessage

if TYPE_CHECKING:
    from app.models.project import Project

logger = logging.getLogger(__name__)


# ── Connection Manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """
    Singleton that manages the mapping of project_id → (WebSocket, Process).

    Design decisions:
      - One active WebSocket per project (simplifies reconnect logic).
        A second connect from the same project kills the existing session.
      - One running OpenCode process per project at a time.
        Concurrent prompts are queued by rejecting new ones while busy.
    """

    def __init__(self) -> None:
        # project_id → WebSocket
        self._connections: dict[uuid.UUID, WebSocket] = {}
        # project_id → asyncio subprocess
        self._processes: dict[uuid.UUID, asyncio.subprocess.Process] = {}

    # ── WebSocket lifecycle ───────────────────────────────────────────────────

    async def connect(self, project_id: uuid.UUID, websocket: WebSocket) -> None:
        """Accept a new WebSocket, replacing any pre-existing connection."""
        await websocket.accept()

        # If a stale session exists, close it gracefully before replacing
        if project_id in self._connections:
            logger.info("Replacing stale WS connection for project %s", project_id)
            try:
                await self._connections[project_id].close(code=1001)
            except Exception:
                pass

        self._connections[project_id] = websocket
        logger.info("WS connected: project=%s", project_id)

    async def disconnect(self, project_id: uuid.UUID) -> None:
        """Tear down the WebSocket and terminate any running subprocess."""
        self._connections.pop(project_id, None)
        await self._terminate_process(project_id)
        logger.info("WS disconnected: project=%s", project_id)

    # ── Messaging ─────────────────────────────────────────────────────────────

    async def send(self, project_id: uuid.UUID, message: WsOutgoingMessage) -> None:
        """Send a JSON message to the connected client, if still connected."""
        ws = self._connections.get(project_id)
        if ws is None:
            return
        try:
            await ws.send_json(message.model_dump(exclude_none=True))
        except Exception as exc:
            logger.warning("Failed to send WS message to project %s: %s", project_id, exc)

    # ── Process management ────────────────────────────────────────────────────

    def is_busy(self, project_id: uuid.UUID) -> bool:
        proc = self._processes.get(project_id)
        return proc is not None and proc.returncode is None

    def register_process(
        self, project_id: uuid.UUID, proc: asyncio.subprocess.Process
    ) -> None:
        self._processes[project_id] = proc

    def unregister_process(self, project_id: uuid.UUID) -> None:
        self._processes.pop(project_id, None)

    async def _terminate_process(self, project_id: uuid.UUID) -> None:
        proc = self._processes.pop(project_id, None)
        if proc is None:
            return
        if proc.returncode is None:
            logger.info("Terminating OpenCode process for project %s", project_id)
            try:
                proc.terminate()
                # Give it 5 s to exit cleanly before hard-killing
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
            except ProcessLookupError:
                pass


# Global singleton — imported by the workspace router
manager = ConnectionManager()


# ── OpenCode Service ──────────────────────────────────────────────────────────

class OpenCodeService:
    """
    Wraps the OpenCode CLI binary as an async subprocess.
    One instance is shared across the application lifetime.
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._manager = connection_manager

    # ── Public API ────────────────────────────────────────────────────────────

    async def run_prompt(
        self,
        project: "Project",
        prompt: str,
    ) -> None:
        """
        Launch OpenCode for *project* with *prompt*.

        This is intentionally fire-and-forget from the router's perspective:
        the router awaits this coroutine but the coroutine itself streams
        output back via the WebSocket as it arrives.

        Raises:
            ProcessAlreadyRunningError: if a process is already running.
            WorkspaceError:             if the subprocess could not start.
        """
        project_id = project.id

        if self._manager.is_busy(project_id):
            raise ProcessAlreadyRunningError()

        # Decrypt credentials — the plaintext never touches the DB
        try:
            api_key = decrypt_value(project.llm_api_key_encrypted)
        except ValueError as exc:
            raise WorkspaceError(f"Failed to decrypt API key: {exc}") from exc

        workdir = self._workspace_dir(project_id)
        command, env = self._build_command(
            prompt=prompt,
            api_key=api_key,
            base_url=project.llm_base_url,
            model=project.llm_model,
            workdir=workdir,
        )

        await self._manager.send(
            project_id,
            WsOutgoingMessage(type="status", message="Starting OpenCode…"),
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=workdir,
                # Prevent the subprocess from inheriting the parent's terminal
                # so it doesn't try to use readline / interactive prompts.
                start_new_session=True,
            )
        except FileNotFoundError:
            raise WorkspaceError(
                f"OpenCode binary not found at '{command[0]}'. "
                "Check the OPENCODE_BINARY environment variable."
            )
        except OSError as exc:
            raise WorkspaceError(f"Could not start OpenCode: {exc}") from exc

        self._manager.register_process(project_id, proc)
        logger.info(
            "OpenCode started: project=%s pid=%s prompt=%r",
            project_id, proc.pid, prompt[:80],
        )

        settings = get_settings()
        try:
            # Stream stdout and stderr concurrently; wait for both to finish.
            await asyncio.wait_for(
                asyncio.gather(
                    self._stream_stdout(proc, project_id),
                    self._stream_stderr(proc, project_id),
                ),
                timeout=settings.opencode_timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.warning("OpenCode timed out for project %s", project_id)
            proc.terminate()
            await self._manager.send(
                project_id,
                WsOutgoingMessage(
                    type="error",
                    message=f"OpenCode timed out after {settings.opencode_timeout_seconds}s.",
                ),
            )
            return
        finally:
            # Always clean up, even on exception
            self._manager.unregister_process(project_id)

        exit_code = proc.returncode if proc.returncode is not None else -1
        logger.info("OpenCode finished: project=%s exit_code=%s", project_id, exit_code)

        await self._manager.send(
            project_id,
            WsOutgoingMessage(type="complete", exit_code=exit_code),
        )

    # ── Stream helpers ────────────────────────────────────────────────────────

    async def _stream_stdout(
        self,
        proc: asyncio.subprocess.Process,
        project_id: uuid.UUID,
    ) -> None:
        """Read stdout line-by-line and forward each line to the WebSocket."""
        if proc.stdout is None:
            return
        async for raw_line in proc.stdout:
            line = raw_line.decode(errors="replace").rstrip("\n")
            if line:
                await self._manager.send(
                    project_id,
                    WsOutgoingMessage(type="output", stream="stdout", data=line),
                )

    async def _stream_stderr(
        self,
        proc: asyncio.subprocess.Process,
        project_id: uuid.UUID,
    ) -> None:
        """Read stderr line-by-line and forward each line to the WebSocket."""
        if proc.stderr is None:
            return
        async for raw_line in proc.stderr:
            line = raw_line.decode(errors="replace").rstrip("\n")
            if line:
                await self._manager.send(
                    project_id,
                    WsOutgoingMessage(type="output", stream="stderr", data=line),
                )

    # ── Command builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_command(
        prompt: str,
        api_key: str,
        base_url: str,
        model: str | None,
        workdir: str,
    ) -> tuple[list[str], dict[str, str]]:
        """
        Construct the argv list and environment for the OpenCode subprocess.

        ┌─────────────────────────────────────────────────────────────────────┐
        │  SUBPROCESS (default — OpenCode binary on the host/container PATH)  │
        └─────────────────────────────────────────────────────────────────────┘
        Credentials are passed as environment variables, NOT shell arguments,
        so they never appear in `ps` output or shell history.

        argv:  ['opencode', 'run', '<prompt>']
        env:   OPENAI_API_KEY, OPENAI_BASE_URL, OPENCODE_MODEL (if set)

        Adjust the argv if your OpenCode version uses different subcommands,
        e.g. `opencode --prompt "..."` or `opencode chat "..."`.

        ┌─────────────────────────────────────────────────────────────────────┐
        │  DOCKER MODE (future)                                               │
        │  Uncomment this block and comment out the section above to run      │
        │  OpenCode in an isolated container per prompt.                      │
        └─────────────────────────────────────────────────────────────────────┘
        # DOCKER_IMAGE = os.environ.get("OPENCODE_DOCKER_IMAGE", "opencode:latest")
        # command = [
        #     "docker", "run", "--rm",
        #     "--network", "none",              # air-gap the container
        #     "-e", f"OPENAI_API_KEY={api_key}",
        #     "-e", f"OPENAI_BASE_URL={base_url}",
        #     *([ "-e", f"OPENCODE_MODEL={model}"] if model else []),
        #     # MOUNT: bind the project workspace so OpenCode can read/write files
        #     "-v", f"{workdir}:/workspace",
        #     "-w", "/workspace",
        #     DOCKER_IMAGE,
        #     "run", prompt,
        # ]
        # return command, {}   # env is embedded in `-e` flags for docker
        """
        settings = get_settings()

        # Inherit the full host environment so PATH, locale, etc. are available
        env = os.environ.copy()

        # Inject LLM credentials — isolated from argv to avoid shell injection
        env["OPENAI_API_KEY"] = api_key
        env["OPENAI_BASE_URL"] = base_url
        if model:
            env["OPENCODE_MODEL"] = model

        # Build the argv without shell=True to prevent any injection
        command: list[str] = [settings.opencode_binary, "run", prompt]

        return command, env

    @staticmethod
    def _workspace_dir(project_id: uuid.UUID) -> str:
        """Return (and create) the workspace directory for *project_id*."""
        settings = get_settings()
        path = os.path.join(settings.projects_root, str(project_id))
        os.makedirs(path, exist_ok=True)
        return path


# Singleton instance — imported by workspace router
opencode_service = OpenCodeService(manager)
