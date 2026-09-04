"""Dashboard first-paint must not wait on scanners or a blank Loading gate."""

from pathlib import Path

import pytest
from httpx import AsyncClient

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.store import PaperTradeStore

_ROOT = Path(__file__).resolve().parents[2]


def test_access_guard_does_not_wait_on_fetch_me() -> None:
    text = (
        _ROOT / "frontend" / "components" / "product-access-guard.tsx"
    ).read_text(encoding="utf-8")
    enabled = text.split("useQuery")[1].split("staleTime")[0]
    assert "Boolean(user)" not in enabled
    assert "gateQuery.isFetching" not in text


def test_assets_hook_defers_sse_until_snapshot() -> None:
    text = (_ROOT / "frontend" / "hooks" / "use-assets.ts").read_text(encoding="utf-8")
    assert "if (!query.data) return" in text
    assert "ASSETS_SNAPSHOT_KEY" in text


def test_auth_wakes_health_in_parallel() -> None:
    text = (
        _ROOT / "frontend" / "components" / "auth-provider.tsx"
    ).read_text(encoding="utf-8")
    assert "fetchHealth(12_000)" in text
    assert "4 * 60_000" in text


def test_paper_snapshot_from_store_skips_scanners() -> None:
    store = PaperTradeStore()
    summary = PaperAgent.snapshot_from_store(store)
    assert summary.agent_name
    assert summary.optimistic.equity == summary.starting_cash
    assert summary.open_trades == []


@pytest.mark.asyncio
async def test_paper_summary_without_tick_skips_agent(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom() -> None:
        raise AssertionError("paper agent constructed on tick=false summary")

    monkeypatch.setattr("app.api.routes.paper.get_paper_agent", _boom)
    response = await client.get("/api/v1/paper/summary?tick=false")
    assert response.status_code == 200
    body = response.json()
    assert "optimistic" in body
    assert "honest" in body
