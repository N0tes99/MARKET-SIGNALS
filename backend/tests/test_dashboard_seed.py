"""Durable dashboard ranking seed (disk + paper_agent_state)."""

from __future__ import annotations

from app.api.routes import assets as assets_routes
from app.engines.paper_agent.store import PaperTradeStore
from app.schemas.assets import AssetSummary


def _sample() -> AssetSummary:
    return AssetSummary(
        symbol="BTC",
        confidence=72.0,
        trend="Bullish",
        trade_grade="B",
        buyer_strength=61.0,
        risk=38.0,
        expected_value=1.4,
        trade_state="WATCH",
        execution_signal="WATCH",
        asset_class="crypto",
    )


def test_durable_seed_survives_disk_wipe(tmp_path, monkeypatch) -> None:
    store = PaperTradeStore()
    disk = tmp_path / "dash.json"
    monkeypatch.setattr(assets_routes, "_DASHBOARD_STORE", store)
    monkeypatch.setattr(assets_routes, "_DISK_CACHE_PATH", disk)

    assets_routes._persist_summaries([_sample()])
    assert disk.is_file()
    from_disk = assets_routes._read_durable_summaries()
    assert from_disk is not None
    assert from_disk[0].symbol == "BTC"

    disk.unlink()
    from_kv = assets_routes._read_durable_summaries()
    assert from_kv is not None
    assert from_kv[0].symbol == "BTC"
    assert from_kv[0].confidence == 72.0
