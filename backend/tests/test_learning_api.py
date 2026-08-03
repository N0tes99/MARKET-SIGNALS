"""Learning and backtest API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_similarity_endpoint(client: AsyncClient) -> None:
    """Similarity endpoint returns history count and matches list."""
    await client.get("/api/v1/assets/BTC/evidence")
    response = await client.get("/api/v1/assets/BTC/similarity")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert "matches" in data
    assert data["history_count"] >= 1


@pytest.mark.asyncio
async def test_backtest_endpoint(client: AsyncClient) -> None:
    """Backtest endpoint returns performance metrics."""
    response = await client.get("/api/v1/backtests/BTC")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert "win_rate" in data
    assert "total_signals" in data
