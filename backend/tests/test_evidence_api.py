"""Evidence API endpoint tests."""

import pytest
from httpx import AsyncClient

from app.market_data.symbols import TRACKED_SYMBOLS
from app.scoring.weights import DEFAULT_WEIGHTS


@pytest.mark.asyncio
async def test_get_asset_evidence(client: AsyncClient) -> None:
    """Evidence endpoint returns a full bundle for a tracked asset."""
    response = await client.get("/api/v1/assets/BTC/evidence")
    assert response.status_code == 200

    data = response.json()
    assert data["symbol"] == "BTC"
    assert data["timeframe"] == "1h"
    assert data["total_confidence"] > 0
    categories = {item["category"] for item in data["items"]}
    assert categories == {category.value for category in DEFAULT_WEIGHTS}
    assert "id" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_get_asset_evidence_unknown_symbol(client: AsyncClient) -> None:
    """Evidence endpoint returns 404 for untracked assets."""
    response = await client.get("/api/v1/assets/ZZZ/evidence")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_assets_use_evidence_confidence(client: AsyncClient) -> None:
    """Asset summaries reflect decision pipeline scores."""
    response = await client.get("/api/v1/assets")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == len(TRACKED_SYMBOLS)
    assert all(item["confidence"] > 0 for item in data)
    assert all(item["trade_grade"] != "N/A" for item in data)
    assert all("trade_state" in item for item in data)
