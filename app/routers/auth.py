"""
app/routers/auth.py
───────────────────
REST endpoints for the Authentication domain.

Route summary
─────────────
POST /api/v1/auth/register        → create account
POST /api/v1/auth/login           → return JWT
POST /api/v1/auth/forgot-password → generate reset token (mocked)
POST /api/v1/auth/reset-password  → consume token, set new password
GET  /api/v1/auth/me              → return current user info
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserMeResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    Create a new user account.

    - Validates email uniqueness.
    - Hashes the password with bcrypt before storage.
    - Returns the new user's public profile (no password, no token).
    """
    return await auth_service.register_user(payload, db)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT access token",
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange email + password for a JWT access token.

    The token must be sent as `Authorization: Bearer <token>` on
    all protected endpoints.
    """
    return await auth_service.login_user(payload, db)


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password-reset token (mocked — no email sent)",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ForgotPasswordResponse:
    """
    Initiate the password-reset flow.

    **Development mode**: the reset token is returned directly in the response
    body so the flow can be tested without an SMTP server.

    **Production**: remove `reset_token` from the response schema and wire up
    a real email delivery service.  The response should always return the same
    generic message regardless of whether the email exists.
    """
    return await auth_service.forgot_password(payload.email, db)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password using the token from forgot-password",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> ResetPasswordResponse:
    """
    Consume a password-reset token and set a new password.

    The token is single-use and expires after `RESET_TOKEN_EXPIRE_MINUTES`
    (default 30 minutes).
    """
    return await auth_service.reset_password(payload, db)


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Return the current authenticated user's profile",
)
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserMeResponse:
    """Protected endpoint that echoes back the caller's profile."""
    return UserMeResponse.model_validate(current_user)
