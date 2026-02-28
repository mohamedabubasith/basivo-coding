"""
app/dependencies.py
───────────────────
Reusable FastAPI dependency functions.

`get_current_user`  — validates the Bearer JWT and returns the User ORM object.
`get_current_active_user` — additionally enforces that the account is active.

WebSocket note:
  Standard HTTP headers are NOT available during the WebSocket handshake in
  most browser clients.  Instead, the JWT is passed as a query parameter:
      ws://host/api/v1/ws/{project_id}?token=<jwt>
  `get_ws_current_user` handles this pattern.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ForbiddenError,
    InvalidTokenError,
    NotFoundError,
)
from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

# Bearer scheme — auto-generates the OpenAPI "Authorize" button
_bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User:
    """Shared logic: decode JWT → fetch User from DB."""
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise InvalidTokenError()
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise InvalidTokenError()

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise NotFoundError("User")

    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate Bearer token, return the matching User ORM object."""
    if credentials is None:
        raise InvalidTokenError("Authorization header missing.")
    return await _resolve_user_from_token(credentials.credentials, db)


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    """Like get_current_user but also checks `is_active`."""
    if not user.is_active:
        raise ForbiddenError("Your account has been deactivated.")
    return user


async def get_ws_current_user(
    token: str = Query(..., description="JWT access token passed as query param for WS auth."),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    WebSocket-compatible auth dependency.
    The JWT travels as ?token=<jwt> because browser WebSocket APIs
    do not support custom request headers.
    """
    return await _resolve_user_from_token(token, db)
