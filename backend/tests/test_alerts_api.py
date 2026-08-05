"""Alert API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_alert_status(client: AsyncClient) -> None:
    response = await client.get("/api/v1/alerts/status")
    assert response.status_code == 200
    data = response.json()
    assert "enabled" in data
    assert data["min_grade"] == "B"
    assert data["min_confidence"] == 65.0
    assert "discord_configured" in data
    assert "email_configured" in data
