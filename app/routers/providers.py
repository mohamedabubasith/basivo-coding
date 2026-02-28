"""
app/routers/providers.py
─────────────────────────
LLM provider utilities — test connection + fetch available models.

Routes
──────
POST /api/v1/providers/test-connection  → validate API key + return model list
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter
from pydantic import AnyHttpUrl, BaseModel, Field

router = APIRouter(prefix="/providers", tags=["Providers"])


class TestConnectionRequest(BaseModel):
    base_url: AnyHttpUrl = Field(description="OpenAI-compatible base URL")
    api_key: str = Field(description="Your LLM API key")


class TestConnectionResponse(BaseModel):
    success: bool
    models: list[str] = []
    error: str | None = None


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    summary="Test an LLM API key and return available models",
)
async def test_connection(payload: TestConnectionRequest) -> TestConnectionResponse:
    """
    Calls GET {base_url}/models with the provided API key.

    Returns the list of available model IDs on success, or an error message
    on failure.  This is called from the Create Project modal so the user
    can select a model from the dropdown.
    """
    base = str(payload.base_url).rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base}/models",
                headers={
                    "Authorization": f"Bearer {payload.api_key}",
                    "Content-Type": "application/json",
                },
            )

        if resp.status_code == 401:
            return TestConnectionResponse(success=False, error="Invalid API key (401 Unauthorized).")
        if resp.status_code == 404:
            # Some providers don't expose /models — treat as success with no list
            return TestConnectionResponse(
                success=True,
                models=[],
                error="Provider does not expose /models endpoint. Enter model name manually.",
            )
        if not resp.is_success:
            return TestConnectionResponse(
                success=False,
                error=f"Provider returned HTTP {resp.status_code}.",
            )

        data = resp.json()
        models: list[str] = []

        # Standard OpenAI format: {"data": [{"id": "gpt-4o", ...}, ...]}
        if isinstance(data, dict) and "data" in data:
            models = [m["id"] for m in data["data"] if isinstance(m, dict) and "id" in m]
        elif isinstance(data, list):
            # Some providers return a plain list
            models = [m["id"] if isinstance(m, dict) else str(m) for m in data]

        # Sort and deduplicate
        models = sorted(set(models))

        return TestConnectionResponse(success=True, models=models)

    except httpx.ConnectError:
        return TestConnectionResponse(success=False, error="Connection refused. Check the base URL.")
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, error="Request timed out (15s).")
    except Exception as exc:
        return TestConnectionResponse(success=False, error=f"Unexpected error: {exc}")
