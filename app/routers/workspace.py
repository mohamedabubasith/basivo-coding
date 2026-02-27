"""
app/routers/workspace.py
────────────────────────
WebSocket endpoint and workspace status REST endpoint.

Route summary
─────────────
WS  /api/v1/ws/{project_id}?token=<jwt>  → real-time OpenCode session
GET /api/v1/workspace/{project_id}/status → poll process status (REST fallback)

WebSocket message protocol
──────────────────────────
INCOMING (client → server):
  { "type": "prompt", "content": "Create a Vite React app" }
  { "type": "ping" }               -- keepalive

OUTGOING (server → client):
  { "type": "connected",  "message": "..." }          -- handshake ack
  { "type": "status",     "message": "..." }          -- informational
  { "type": "output",     "stream": "stdout"|"stderr", "data": "..." }
  { "type": "complete",   "exit_code": 0 }            -- process finished
  { "type": "error",      "message": "..." }          -- fatal error

Auth strategy
─────────────
Browsers cannot set custom headers during a WebSocket upgrade.  The JWT is
therefore passed as a query parameter: ?token=<jwt>.
The `get_ws_current_user` dependency reads and validates it before the
connection is accepted, so unauthorised handshakes are rejected at the HTTP
101 Switching Protocols layer.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ProcessAlreadyRunningError
from app.database import get_db
from app.dependencies import get_ws_current_user
from app.models.user import User
from app.schemas.project import WsIncomingMessage, WsOutgoingMessage
from app.services.opencode_service import manager, opencode_service
from app.services.project_service import get_project_for_workspace

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Workspace"])


@router.websocket("/ws/{project_id}")
async def workspace_ws(
    project_id: uuid.UUID,
    websocket: WebSocket,
    current_user: User = Depends(get_ws_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Main WebSocket endpoint for a project workspace session.

    Lifecycle:
      1. Auth validated via ?token query param (get_ws_current_user).
      2. Project ownership verified before accepting the connection.
      3. Connection registered in ConnectionManager.
      4. Receive loop: handle 'prompt' and 'ping' message types.
      5. On disconnect / error: teardown connection + running process.

    The OpenCode subprocess is launched per-prompt, not per-connection.
    This means the user can send multiple sequential prompts in one session.
    """
    # Step 1: verify the project exists and belongs to this user
    # Do this BEFORE accepting the WS so we can return an HTTP 403/404
    # if auth fails (the handshake is still HTTP at this point).
    try:
        project = await get_project_for_workspace(project_id, current_user, db)
    except AppError as exc:
        # Reject the handshake with a close frame — FastAPI will return
        # the appropriate HTTP status before the upgrade completes.
        await websocket.close(code=4403, reason=exc.detail)
        return

    # Step 2: accept and register the connection
    await manager.connect(project_id, websocket)

    # Step 3: send handshake confirmation
    await manager.send(
        project_id,
        WsOutgoingMessage(
            type="connected",
            message=f"Connected to project '{project.name}'. Ready for prompts.",
        ),
    )

    # Step 4: receive loop
    try:
        while True:
            raw = await websocket.receive_json()

            # Parse and validate the incoming message shape
            try:
                msg = WsIncomingMessage.model_validate(raw)
            except Exception:
                await manager.send(
                    project_id,
                    WsOutgoingMessage(
                        type="error",
                        message="Invalid message format. Expected {type, content}.",
                    ),
                )
                continue

            # ── Handle message types ──────────────────────────────────────────

            if msg.type == "ping":
                # Keepalive — browser sends pings to prevent idle disconnects
                await manager.send(
                    project_id, WsOutgoingMessage(type="status", message="pong")
                )
                continue

            if msg.type == "prompt":
                if not msg.content or not msg.content.strip():
                    await manager.send(
                        project_id,
                        WsOutgoingMessage(type="error", message="Prompt cannot be empty."),
                    )
                    continue

                # Guard: reject if a process is already running
                if manager.is_busy(project_id):
                    await manager.send(
                        project_id,
                        WsOutgoingMessage(
                            type="error",
                            message="OpenCode is already running. Wait for it to finish.",
                        ),
                    )
                    continue

                # Launch OpenCode — this awaits until the process exits,
                # streaming output to the WebSocket as it runs.
                try:
                    await opencode_service.run_prompt(
                        project=project,
                        prompt=msg.content.strip(),
                    )
                except ProcessAlreadyRunningError as exc:
                    await manager.send(
                        project_id, WsOutgoingMessage(type="error", message=exc.detail)
                    )
                except AppError as exc:
                    await manager.send(
                        project_id, WsOutgoingMessage(type="error", message=exc.detail)
                    )
                except Exception as exc:
                    logger.exception(
                        "Unexpected error running OpenCode for project %s", project_id
                    )
                    await manager.send(
                        project_id,
                        WsOutgoingMessage(type="error", message=f"Internal error: {exc}"),
                    )
                continue

            # Unknown message type
            await manager.send(
                project_id,
                WsOutgoingMessage(
                    type="error",
                    message=f"Unknown message type: {msg.type!r}",
                ),
            )

    except WebSocketDisconnect:
        logger.info("Client disconnected from project %s", project_id)
    except Exception:
        logger.exception("Unexpected error in WS handler for project %s", project_id)
    finally:
        # Step 5: always clean up
        await manager.disconnect(project_id)


# ── REST status endpoint (polling fallback) ───────────────────────────────────

@router.get(
    "/workspace/{project_id}/status",
    tags=["Workspace"],
    summary="Check whether an OpenCode process is currently running",
)
async def workspace_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_ws_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    REST fallback for clients that cannot use WebSockets.

    Returns a simple JSON object indicating whether an OpenCode process
    is currently running for this project.
    """
    # Verify ownership before exposing status
    await get_project_for_workspace(project_id, current_user, db)

    return {
        "project_id": str(project_id),
        "is_busy": manager.is_busy(project_id),
        "connected": project_id in manager._connections,
    }
