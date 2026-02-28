"""
app/routers/terminal.py
────────────────────────
PTY-backed interactive terminal over WebSocket.

Route
─────
WS /api/v1/projects/{id}/terminal?token=<jwt>

WebSocket message protocol
──────────────────────────
INCOMING (client → server):
  { "type": "input",  "data": "<keystrokes>" }         — keyboard input
  { "type": "resize", "cols": 120, "rows": 36 }        — terminal resize

OUTGOING (server → client):
  { "type": "output", "data": "<terminal output>" }    — terminal output
  { "type": "exit",   "code": 0 }                      — shell exited
  { "type": "error",  "message": "..." }               — launch error
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import pty
import struct
import termios
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.dependencies import get_ws_current_user
from app.models.user import User
from app.services.project_service import _fetch_and_authorize

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Terminal"])


def _workspace(project_id: uuid.UUID) -> str:
    settings = get_settings()
    path = os.path.join(settings.projects_root, str(project_id))
    os.makedirs(path, exist_ok=True)
    return path


def _set_winsize(fd: int, cols: int, rows: int) -> None:
    size = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)
    except OSError:
        pass


@router.websocket("/projects/{project_id}/terminal")
async def terminal_ws(
    project_id: uuid.UUID,
    websocket: WebSocket,
    current_user: User = Depends(get_ws_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Interactive PTY terminal for a project workspace."""
    try:
        await _fetch_and_authorize(project_id, current_user, db)
    except Exception as exc:
        await websocket.close(code=4403, reason=str(exc))
        return

    await websocket.accept()
    workdir = _workspace(project_id)

    # ── Spawn a PTY-backed bash shell ─────────────────────────────────────────
    master_fd, slave_fd = pty.openpty()
    _set_winsize(master_fd, 220, 50)

    try:
        env = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "HOME": os.environ.get("HOME", "/root"),
            "SHELL": "/bin/bash",
        }
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-i",
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            cwd=workdir,
            close_fds=True,
        )
    except Exception as exc:
        os.close(master_fd)
        os.close(slave_fd)
        await websocket.send_json({"type": "error", "message": f"Failed to spawn shell: {exc}"})
        await websocket.close()
        return

    # Parent doesn't need the slave end
    os.close(slave_fd)
    logger.info("Terminal spawned: project=%s pid=%s workdir=%s", project_id, proc.pid, workdir)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    # ── PTY → WebSocket reader ────────────────────────────────────────────────
    async def pty_to_ws() -> None:
        while not stop_event.is_set():
            try:
                # Non-blocking read via the event loop's file descriptor reader
                fut: asyncio.Future[bytes] = loop.create_future()

                def _on_readable() -> None:
                    try:
                        data = os.read(master_fd, 4096)
                        if not fut.done():
                            fut.set_result(data)
                    except OSError as e:
                        if not fut.done():
                            fut.set_exception(e)
                    loop.remove_reader(master_fd)

                loop.add_reader(master_fd, _on_readable)
                try:
                    data = await asyncio.wait_for(fut, timeout=0.5)
                    await websocket.send_json(
                        {"type": "output", "data": data.decode(errors="replace")}
                    )
                except asyncio.TimeoutError:
                    # No data yet — check if process exited
                    if proc.returncode is not None:
                        break
                    loop.remove_reader(master_fd)
                except OSError:
                    # PTY master closed (shell exited)
                    break
            except Exception:
                break

        exit_code = proc.returncode if proc.returncode is not None else 0
        try:
            await websocket.send_json({"type": "exit", "code": exit_code})
        except Exception:
            pass
        stop_event.set()

    # ── WebSocket → PTY writer ─────────────────────────────────────────────────
    async def ws_to_pty() -> None:
        while not stop_event.is_set():
            try:
                msg = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                break
            except Exception:
                break

            msg_type = msg.get("type")
            if msg_type == "input":
                data = msg.get("data", "")
                if data:
                    try:
                        os.write(master_fd, data.encode())
                    except OSError:
                        break
            elif msg_type == "resize":
                cols = int(msg.get("cols", 80))
                rows = int(msg.get("rows", 24))
                _set_winsize(master_fd, cols, rows)

        stop_event.set()

    # ── Run both tasks concurrently ────────────────────────────────────────────
    try:
        await asyncio.gather(pty_to_ws(), ws_to_pty())
    finally:
        stop_event.set()
        # Kill the shell if still alive
        if proc.returncode is None:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                proc.kill()
        try:
            os.close(master_fd)
        except OSError:
            pass
        logger.info("Terminal session ended: project=%s", project_id)
