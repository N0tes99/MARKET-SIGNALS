"""Weight tuning API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_optimize_weights_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/tuning/optimize/BTC")
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "BTC"
    assert data["recommended_preset"]
    assert len(data["results"]) >= 5


@pytest.mark.asyncio
async def test_apply_and_reset_weights(client: AsyncClient) -> None:
    optimize = await client.get("/api/v1/tuning/optimize/BTC")
    preset = optimize.json()["recommended_preset"]

    applied = await client.post("/api/v1/tuning/weights/apply", json={"preset": preset})
    assert applied.status_code == 200
    body = applied.json()
    assert body["preset"] == preset
    if preset != "default":
        assert body["regime_auto"] is False

    reset = await client.post("/api/v1/tuning/weights/reset")
    assert reset.status_code == 200
    assert reset.json()["preset"] == "default"
    assert reset.json()["regime_auto"] is True
