"""
app/services/auth_service.py
────────────────────────────
Business logic for:
  - User registration
  - Login (returns JWT)
  - Forgot-password  (generates & stores reset token)
  - Reset-password   (validates token, sets new password)

All database I/O goes through AsyncSession so every call is non-blocking.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    UserAlreadyExistsError,
)
from app.core.security import (
    create_access_token,
    create_reset_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
)


async def register_user(payload: RegisterRequest, db: AsyncSession) -> RegisterResponse:
    """
    Create a new user account.

    Raises:
        UserAlreadyExistsError: if the email is already taken.
    """
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise UserAlreadyExistsError()

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()   # get the generated UUID before commit
    await db.refresh(user)

    return RegisterResponse.model_validate(user)


async def login_user(payload: LoginRequest, db: AsyncSession) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.

    Raises:
        InvalidCredentialsError: on any auth failure (intentionally vague).
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always run verify_password even on missing user to avoid timing attacks
    dummy_hash = "$2b$12$dummyhashfortimingnopurposeatall"
    candidate_hash = user.hashed_password if user else dummy_hash

    if not verify_password(payload.password, candidate_hash) or user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InvalidCredentialsError("Account is deactivated.")

    settings = get_settings()
    access_token = create_access_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


async def forgot_password(email: str, db: AsyncSession) -> ForgotPasswordResponse:
    """
    Generate a password-reset token for *email* (if it exists).

    Security: always returns the same generic message regardless of whether
    the email exists, to prevent user enumeration.

    In production:
      1. Send the token via email (e.g. SendGrid / SES).
      2. Remove `reset_token` from `ForgotPasswordResponse`.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    raw_token: str | None = None

    if user is not None:
        raw_token, expires_at = create_reset_token()
        user.reset_token = raw_token
        user.reset_token_expires_at = expires_at
        # flush so the session writes — outer commit() in get_db() persists it
        await db.flush()

    # PRODUCTION TODO: send email here with a link containing `raw_token`
    # e.g.:  await email_service.send_reset_link(user.email, raw_token)

    return ForgotPasswordResponse(
        reset_token=raw_token,  # REMOVE IN PRODUCTION
    )


async def reset_password(payload: ResetPasswordRequest, db: AsyncSession) -> ResetPasswordResponse:
    """
    Consume a reset token and update the user's password.

    Raises:
        InvalidTokenError:  token not found in DB.
        TokenExpiredError:  token exists but has expired.
    """
    result = await db.execute(
        select(User).where(User.reset_token == payload.token)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise InvalidTokenError("Reset token is invalid.")

    now = datetime.now(timezone.utc)
    if user.reset_token_expires_at is None or user.reset_token_expires_at < now:
        raise TokenExpiredError("Reset token has expired. Please request a new one.")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    await db.flush()

    return ResetPasswordResponse()
