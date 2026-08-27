"""Tests for cortex brain orchestrator and episodic memory."""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.cortex.attention import specialists_for_state
from app.cortex.orchestrator import CortexOrchestrator
from app.cortex.synthesis import alert_level_for
from app.engines.expansion_engine.types import (
    CompressionResult,
    ExpansionCandidate,
    ExpansionState,
    SqueezeFuelResult,
    TriggerResult,
)
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService
from app.memory.episodic.store import InMemoryEpisodicStore, serialize_working_memory


def _minimal_expansion(symbol: str, state: ExpansionState, net: float) -> ExpansionCandidate:
    comp = CompressionResult(
        score=88.0,
        atr_percentile=5.0,
        bb_width_percentile=8.0,
        range_compression_pct=90.0,
        volume_compression_pct=70.0,
        factors=["compressed"],
    )
    squeeze = SqueezeFuelResult(score=70.0, direction="up", factors=["fuel"])
    trigger = TriggerResult(
        active=False,
        direction="neutral",
        volume_ratio=1.0,
        breakout_level=None,
    )
    return ExpansionCandidate(
        id=f"{symbol.lower()}-test",
        symbol=symbol,
        state=state,
        direction_bias="up",
        up_score=net,
        down_score=20.0,
        net_score=net,
        confidence="medium",
        setup_level="high",
        trigger_active=False,
        horizon="1h–12h",
        invalidation="test",
        key_trigger="test",
        compression=comp,
        squeeze=squeeze,
        trigger=trigger,
        as_of=datetime.now(UTC),
    )


def test_attention_routes_default_specialists() -> None:
    specs = specialists_for_state(ExpansionState.DORMANT)
    assert "expansion" in specs
    assert "regime" in specs
    assert "derivatives" in specs
    assert "cvd" in specs
    assert "news" in specs


def test_alert_level_for_primed() -> None:
    exp = _minimal_expansion("SOL", ExpansionState.PRIMED, net=80.0)
    assert alert_level_for(exp) == "primed"


def test_episodic_store_ring_buffer() -> None:
    from app.cortex.types import SymbolContext, WorkingMemory

    store = InMemoryEpisodicStore(max_records=3)
    for i in range(5):
        mem = WorkingMemory(
            tick_id=f"t{i}",
            as_of=datetime.now(UTC),
            universe=("BTC",),
            symbols={"BTC": SymbolContext(symbol="BTC")},
            notes=[f"note-{i}"],
        )
        store.append(mem)
    assert len(store.history(limit=10)) == 3
    assert store.latest() is not None
    assert store.latest().tick_id == "t4"


def test_serialize_working_memory() -> None:
    from app.cortex.types import SymbolContext, WorkingMemory

    exp = _minimal_expansion("BTC", ExpansionState.PRIMED, 78.0)
    mem = WorkingMemory(
        tick_id="abc",
        as_of=datetime.now(UTC),
        universe=("BTC",),
        symbols={"BTC": SymbolContext(symbol="BTC", expansion=exp, alert_level="primed")},
    )
    payload = serialize_working_memory(mem)
    assert payload["tick_id"] == "abc"
    assert "BTC" in payload["symbols"]
    assert payload["symbols"]["BTC"]["expansion"]["state"] == "primed"


def test_orchestrator_tick_with_mock_market() -> None:
    market = MarketDataService(provider=MockMarketDataProvider())
    orch = CortexOrchestrator(market_data=market, episodic=InMemoryEpisodicStore())
    memory = orch.tick(symbols=("BTC",), persist=True)
    assert memory.tick_id
    assert "BTC" in memory.symbols
    assert len(memory.symbols["BTC"].opinions) >= 1
    assert orch.last_memory is not None
    assert orch.episodic.latest() is not None
    assert memory.phase == "cortex_v2"
    names = {o.specialist for o in memory.symbols["BTC"].opinions}
    assert "expansion" in names or len(memory.symbols["BTC"].opinions) >= 1
    assert any(o.specialist == "macro" for o in memory.global_opinions)


@pytest.mark.asyncio
async def test_cortex_api_tick(client: AsyncClient) -> None:
    response = await client.post("/api/v1/cortex/tick")
    assert response.status_code == 200
    body = response.json()
    assert body["memory"]["tick_id"]
    assert body["memory"]["symbols"]


@pytest.mark.asyncio
async def test_cortex_api_get_state(client: AsyncClient) -> None:
    await client.post("/api/v1/cortex/tick")
    response = await client.get("/api/v1/cortex")
    assert response.status_code == 200
    body = response.json()
    assert "digest" in body
    assert body["universe"]


@pytest.mark.asyncio
async def test_cortex_api_history(client: AsyncClient) -> None:
    await client.post("/api/v1/cortex/tick")
    response = await client.get("/api/v1/cortex/history?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1


@pytest.mark.asyncio
async def test_cortex_api_health_and_semantic(client: AsyncClient) -> None:
    await client.post("/api/v1/cortex/tick")
    health = await client.get("/api/v1/cortex/health")
    assert health.status_code == 200
    assert "ticks_recorded" in health.json()
    semantic = await client.get("/api/v1/cortex/semantic")
    assert semantic.status_code == 200
    assert "stats" in semantic.json()


@pytest.mark.asyncio
async def test_expansion_policy_and_warehouse_api(client: AsyncClient) -> None:
    policy = await client.get("/api/v1/expansion/policy")
    assert policy.status_code == 200
    body = policy.json()
    assert body["source"] in {"file", "memory", "postgres"}
    assert "trigger_net_score" in body["knobs"]
    lake = await client.get("/api/v1/data-lake/ohlcv/BTC?timeframe=1h")
    assert lake.status_code == 200
    assert "bars" in lake.json()
    status = await client.get("/api/v1/data-lake/status")
    assert status.status_code == 200
    body = status.json()
    assert "warehouse" in body
    assert "alembic" in body
    assert body["alembic"]["head"]
