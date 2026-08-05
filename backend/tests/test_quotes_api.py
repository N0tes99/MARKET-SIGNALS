"""Quote API tests."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_quotes(client: AsyncClient) -> None:
    response = await client.get("/api/v1/quotes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    sample = data[0]
    assert "symbol" in sample
    assert "price" in sample
    assert "change_pct" in sample
    assert "available" in sample
