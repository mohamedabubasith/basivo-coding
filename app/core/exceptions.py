"""
app/core/exceptions.py
──────────────────────
Domain-specific exceptions and the FastAPI exception handlers that map them
to proper HTTP responses.

Register the handlers in main.py:
    app.add_exception_handler(AppError, app_error_handler)
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ── Base ──────────────────────────────────────────────────────────────────────

class AppError(Exception):
    """Base class for all application-layer exceptions."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Auth errors ───────────────────────────────────────────────────────────────

class InvalidCredentialsError(AppError):
    def __init__(self, detail: str = "Invalid email or password."):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)


class TokenExpiredError(AppError):
    def __init__(self, detail: str = "Token has expired."):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)


class InvalidTokenError(AppError):
    def __init__(self, detail: str = "Invalid or malformed token."):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)


class UserAlreadyExistsError(AppError):
    def __init__(self, detail: str = "A user with this email already exists."):
        super().__init__(detail, status.HTTP_409_CONFLICT)


# ── Resource errors ───────────────────────────────────────────────────────────

class NotFoundError(AppError):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found.", status.HTTP_404_NOT_FOUND)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "You do not have permission to access this resource."):
        super().__init__(detail, status.HTTP_403_FORBIDDEN)


# ── Workspace / OpenCode errors ───────────────────────────────────────────────

class WorkspaceError(AppError):
    def __init__(self, detail: str = "Workspace operation failed."):
        super().__init__(detail, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProcessAlreadyRunningError(AppError):
    def __init__(self):
        super().__init__(
            "An OpenCode process is already running for this project.",
            status.HTTP_409_CONFLICT,
        )


# ── FastAPI exception handler ─────────────────────────────────────────────────

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError subclasses into structured JSON HTTP responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Convenience function — call from main.py."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
