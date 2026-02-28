"""
app/core/security.py
────────────────────
Three independent security concerns live here:

1. Password hashing  — bcrypt via passlib
2. JWT tokens        — python-jose (HS256)
3. Field encryption  — Fernet symmetric encryption for API keys at rest

All functions are stateless and can be imported anywhere.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# ── Password hashing ──────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return _pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Sign and return a JWT access token.

    :param subject:      The `sub` claim — typically the user UUID as a string.
    :param extra_claims: Optional additional claims merged into the payload.
    """
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.  Raises JWTError on any failure
    (expired, tampered, wrong algorithm, etc.).
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


def create_reset_token() -> tuple[str, datetime]:
    """
    Generate a cryptographically secure password-reset token.

    Returns:
        (token_hex, expires_at) — store the hex in the DB, send it to the user.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.reset_token_expire_minutes
    )
    return token, expires_at


# ── Fernet field encryption ───────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """Return a Fernet instance backed by the configured encryption key."""
    settings = get_settings()
    # The key must be URL-safe base64-encoded 32 bytes — exactly what
    # Fernet.generate_key() produces.  We accept it as a plain string.
    key_bytes = settings.encryption_key.encode()
    return Fernet(key_bytes)


def encrypt_value(plain: str) -> str:
    """
    Encrypt *plain* text and return a base64-encoded ciphertext string.
    Safe to store in a TEXT column.
    """
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """
    Decrypt a value previously encrypted with :func:`encrypt_value`.
    Raises :class:`cryptography.fernet.InvalidToken` if the ciphertext is
    tampered with or the wrong key is used.
    """
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        raise ValueError("API key decryption failed — invalid token or wrong key.")
