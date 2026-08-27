"""Health endpoint tests."""

import pytest
from httpx import AsyncClient

from app.market_data.symbols import TRACKED_SYMBOLS, TRACKED_SYMBOLS_SET


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """Health endpoint returns healthy status with expected fields."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == "Signal Engine"
    assert data["version"] == "0.1.0"
    assert "environment" in data
    assert "stores" in data
    assert data["stores"]["learning"] in {"memory", "postgres"}
    assert data["stores"]["paper"] in {"memory", "postgres"}
    assert data["stores"]["alerts"] in {"memory", "postgres"}
    assert data["warehouse"]["backend"] in {"memory", "postgres"}
    assert "bar_count" in data["warehouse"]
    assert data["alembic"]["head"]
    assert data["alembic"]["source"] in {"skipped", "postgres", "missing", "error"}


@pytest.mark.asyncio
async def test_list_assets(client: AsyncClient) -> None:
    """Assets endpoint returns tracked dashboard assets (sync fills ranks)."""
    response = await client.get("/api/v1/assets?sync=true")
    assert response.status_code == 200

    payload = response.json()
    assert payload["ranking_status"] in {"fresh", "stale", "warming"}
    data = payload["assets"]
    assert len(data) == len(TRACKED_SYMBOLS)
    symbols = {item["symbol"] for item in data}
    assert symbols == TRACKED_SYMBOLS_SET


@pytest.mark.asyncio
async def test_list_opportunities(client: AsyncClient) -> None:
    """Opportunities endpoint returns ranked pipeline results."""
    response = await client.get("/api/v1/opportunities")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == len(TRACKED_SYMBOLS)
    valid_states = {"IGNORE", "WATCH", "EXECUTE", "MANAGE", "EXIT"}
    assert all(item["trade_state"] in valid_states for item in data)
    assert all(item["trade_grade"] != "N/A" for item in data)
