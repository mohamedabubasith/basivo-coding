"""
app/schemas/auth.py
───────────────────
Pydantic v2 request / response schemas for the Authentication domain.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Register ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=8,
        max_length=72,   # bcrypt practical limit
        description="Minimum 8 characters.",
    )

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        """Enforce at least one uppercase, one lowercase, and one digit."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ── Forgot / Reset Password (mocked) ─────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """
    In a real system this would send an email; here we return the token
    directly so the flow can be exercised without an SMTP server.
    The `reset_token` field should be REMOVED once real email delivery is wired.
    """
    message: str = "If that email exists, a reset link has been sent."
    # REMOVE IN PRODUCTION — exposed only for local development / testing
    reset_token: str | None = Field(
        default=None,
        description="Dev-only: the raw reset token. Remove in production.",
    )


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        return v


class ResetPasswordResponse(BaseModel):
    message: str = "Password has been reset successfully."


# ── Current user ──────────────────────────────────────────────────────────────

class UserMeResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
