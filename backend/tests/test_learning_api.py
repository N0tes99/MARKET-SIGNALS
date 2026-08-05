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


@pytest.mark.asyncio
async def test_log_and_resolve_outcome(client: AsyncClient) -> None:
    """Log current signal then resolve as a win with realized return."""
    log = await client.post("/api/v1/assets/SPY/signals/log")
    assert log.status_code == 200
    record = log.json()
    assert record["symbol"] == "SPY"
    assert record["outcome"] is None
    assert "id" in record

    patch = await client.patch(
        f"/api/v1/assets/SPY/signals/{record['id']}/outcome",
        json={"outcome": "win", "realized_return_pct": 0.4, "notes": "SPY +3pts"},
    )
    assert patch.status_code == 200
    resolved = patch.json()
    assert resolved["outcome"] == "win"
    assert resolved["realized_return_pct"] == 0.4

    stats = await client.get("/api/v1/assets/SPY/outcomes/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["wins"] >= 1
    assert body["win_rate"] > 0
