"""
tests/test_auth.py
──────────────────
Tests for the Authentication domain.

Covers:
  - Registration (happy path + duplicate email)
  - Login (happy path + wrong password)
  - Forgot-password / Reset-password flow
  - /auth/me returns current user
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestRegister:
    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "Secret123"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert "id" in body
        assert "hashed_password" not in body

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "Secret123"},
        )
        assert resp.status_code == 409

    async def test_register_weak_password(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "alllower1"},
        )
        assert resp.status_code == 422   # Pydantic validation error

    async def test_register_invalid_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "Secret123"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "Secret123"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    async def test_login_wrong_password(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "WrongPass1"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "Secret123"},
        )
        assert resp.status_code == 401


class TestForgotResetPassword:
    async def test_forgot_returns_token_in_dev(self, client: AsyncClient, registered_user: dict):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )
        assert resp.status_code == 200
        body = resp.json()
        # Dev mode exposes the token
        assert body["reset_token"] is not None

    async def test_forgot_unknown_email_same_response(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        # Same status regardless of whether email exists (anti-enumeration)
        assert resp.status_code == 200
        body = resp.json()
        assert body["reset_token"] is None

    async def test_reset_password_full_flow(self, client: AsyncClient, registered_user: dict):
        # Step 1: get reset token
        forgot_resp = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "test@example.com"},
        )
        token = forgot_resp.json()["reset_token"]

        # Step 2: reset with token
        reset_resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "NewSecret456"},
        )
        assert reset_resp.status_code == 200

        # Step 3: login with new password
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "NewSecret456"},
        )
        assert login_resp.status_code == 200

    async def test_reset_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "invalid-token", "new_password": "NewSecret456"},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_authenticated(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    async def test_me_unauthenticated(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401
