"""
tests/test_projects.py
──────────────────────
Tests for the Project Management domain.

Covers:
  - Create project (happy path + missing fields)
  - List projects
  - Get project by ID (own vs another user's)
  - Delete project
  - API key is never returned in responses
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

PROJECT_PAYLOAD = {
    "name": "My Vite App",
    "description": "Test project",
    "llm_base_url": "https://api.openai.com/v1",
    "llm_api_key": "sk-test-1234567890",
    "llm_model": "gpt-4o",
}


class TestCreateProject:
    async def test_create_success(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post("/api/v1/projects", json=PROJECT_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "My Vite App"
        assert body["api_key_set"] is True
        # The raw API key must NEVER appear in the response
        assert "llm_api_key" not in body
        assert "llm_api_key_encrypted" not in body

    async def test_create_requires_auth(self, client: AsyncClient):
        resp = await client.post("/api/v1/projects", json=PROJECT_PAYLOAD)
        assert resp.status_code == 401

    async def test_create_missing_required_fields(self, client: AsyncClient, auth_headers: dict):
        resp = await client.post(
            "/api/v1/projects",
            json={"name": "Incomplete"},   # missing llm_base_url, llm_api_key
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestListProjects:
    async def test_list_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/projects", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["projects"] == []

    async def test_list_after_create(self, client: AsyncClient, auth_headers: dict):
        await client.post("/api/v1/projects", json=PROJECT_PAYLOAD, headers=auth_headers)
        resp = await client.get("/api/v1/projects", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestGetProject:
    async def test_get_own_project(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/projects", json=PROJECT_PAYLOAD, headers=auth_headers
        )
        project_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == project_id

    async def test_get_nonexistent(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_api_key_not_in_response(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/projects", json=PROJECT_PAYLOAD, headers=auth_headers
        )
        project_id = create_resp.json()["id"]
        get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        body = get_resp.json()
        assert "llm_api_key" not in body
        assert "llm_api_key_encrypted" not in body
        assert body["api_key_set"] is True


class TestDeleteProject:
    async def test_delete_own_project(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/projects", json=PROJECT_PAYLOAD, headers=auth_headers
        )
        project_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/projects/{project_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_nonexistent(self, client: AsyncClient, auth_headers: dict):
        resp = await client.delete(
            "/api/v1/projects/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert resp.status_code == 404
