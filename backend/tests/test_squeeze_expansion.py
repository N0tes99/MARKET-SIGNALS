"""Paper squeeze_expansion feed — cortex TRIGGER/EXPANSION only."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.cortex.types import SymbolContext, WorkingMemory
from app.engines.expansion_engine.types import (
    CompressionResult,
    ExpansionCandidate,
    ExpansionState,
    SqueezeFuelResult,
    TriggerResult,
)
from app.engines.paper_agent.agent import PaperAgent, _fingerprint
from app.engines.paper_agent.squeeze_expansion import (
    SETUP_TYPE,
    SOURCE,
    idea_from_candidate,
    ideas_from_working_memory,
    is_tradeable,
    scan_squeeze_expansion,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade


class _EmptyFeed:
    def scan_feed(self, **_kwargs):
        return []


class _Market:
    def get_ticker(self, symbol):
        return SimpleNamespace(price=100.0)

    def safe_get_ohlcv(self, symbol, timeframe, limit=96):
        return None


def _candidate(
    *,
    symbol: str = "SOL",
    state: ExpansionState = ExpansionState.TRIGGERING,
    net: float = 87.0,
    direction: str = "up",
    trigger_active: bool = True,
) -> ExpansionCandidate:
    comp = CompressionResult(
        score=88.0,
        atr_percentile=5.0,
        bb_width_percentile=8.0,
        range_compression_pct=90.0,
        volume_compression_pct=70.0,
        factors=["compressed"],
    )
    squeeze = SqueezeFuelResult(score=90.0, direction="up", factors=["fuel"])
    trigger = TriggerResult(
        active=trigger_active,
        direction="up" if direction == "up" else "down",
        volume_ratio=1.8,
        breakout_level=100.0,
        factors=["breakout"],
    )
    return ExpansionCandidate(
        id=f"{symbol.lower()}-test",
        symbol=symbol,
        state=state,
        direction_bias=direction,  # type: ignore[arg-type]
        up_score=net,
        down_score=18.0,
        net_score=net,
        confidence="high",
        setup_level="high",
        trigger_active=trigger_active,
        horizon="15m–4h",
        invalidation="test",
        key_trigger="volume confirm",
        compression=comp,
        squeeze=squeeze,
        trigger=trigger,
        factors=["compression", "squeeze"],
        as_of=datetime.now(UTC),
    )


def test_primed_is_not_tradeable() -> None:
    primed = _candidate(state=ExpansionState.PRIMED, net=82.0, trigger_active=False)
    assert is_tradeable(primed) is False
    assert idea_from_candidate(primed) is None


def test_triggering_high_score_is_tradeable() -> None:
    firing = _candidate()
    assert is_tradeable(firing) is True
    idea = idea_from_candidate(firing, tick_id="abc")
    assert idea is not None
    assert idea.direction == "long"
    assert idea.setup_type == SETUP_TYPE
    assert idea.extras["tick_id"] == "abc"
    assert idea.extras["expansion_state"] == "triggering"


def test_ideas_from_memory_skip_dormant() -> None:
    mem = WorkingMemory(
        tick_id="t1",
        as_of=datetime.now(UTC),
        universe=("BTC", "SOL"),
        symbols={
            "BTC": SymbolContext(
                symbol="BTC",
                expansion=_candidate(symbol="BTC", state=ExpansionState.DORMANT, net=20.0),
                alert_level="none",
            ),
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=_candidate(symbol="SOL"),
                alert_level="trigger",
            ),
        },
    )
    ideas = ideas_from_working_memory(mem)
    assert [i.symbol for i in ideas] == ["SOL"]


class _Cortex:
    def __init__(self, memory: WorkingMemory) -> None:
        self.last_memory = memory

    def tick(self, *, persist: bool = True) -> WorkingMemory:
        del persist
        return self.last_memory


def test_scan_uses_last_memory() -> None:
    mem = WorkingMemory(
        tick_id="t9",
        as_of=datetime.now(UTC),
        universe=("SUI",),
        symbols={
            "SUI": SymbolContext(
                symbol="SUI",
                expansion=_candidate(symbol="SUI"),
                alert_level="expansion",
            )
        },
    )
    ideas = scan_squeeze_expansion(_Cortex(mem))
    assert len(ideas) == 1
    assert ideas[0].symbol == "SUI"
    assert ideas[0].extras["alert_level"] == "expansion"


def test_agent_opens_squeeze_expansion(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.scan_crypto_perp_v2", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas", lambda *a, **k: []
    )
    mem = WorkingMemory(
        tick_id="tick-sol",
        as_of=datetime.now(UTC),
        universe=("SOL",),
        symbols={
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=_candidate(symbol="SOL"),
                alert_level="trigger",
            )
        },
    )
    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=PaperTradeStore(),
        pipeline=None,
        size_usd=2500.0,
        cortex=_Cortex(mem),
    )
    notes = agent.tick()
    assert any(n.startswith("open:SOL:squeeze_expansion") for n in notes)
    trade = agent.store.list_all()[0]
    assert trade.source == SOURCE
    assert trade.setup_type == SETUP_TYPE
    assert trade.direction == "long"
    assert trade.policy["features"]["tick_id"] == "tick-sol"
    assert trade.policy["features"]["expansion_state"] == "triggering"
    assert _fingerprint(SOURCE, "SOL", SETUP_TYPE, "long") == trade.fingerprint


def test_agent_squeeze_expansion_daily_cap(monkeypatch) -> None:
    monkeypatch.setattr("app.engines.paper_agent.agent.scan_crypto_perp_v2", lambda *a, **k: [])
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.scan_cme_paper_ideas", lambda *a, **k: []
    )
    now = datetime.now(UTC)
    store = PaperTradeStore()
    store.upsert(
        PaperTrade(
            id=str(uuid4()),
            symbol="BTC",
            source=SOURCE,  # type: ignore[arg-type]
            setup_type=SETUP_TYPE,
            direction="long",
            fingerprint=_fingerprint(SOURCE, "BTC", SETUP_TYPE, "long"),
            signal_at=now,
            confidence=85.0,
            opportunity_score=85.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=100.0,
            optimistic_entry_at=now,
        )
    )
    mem = WorkingMemory(
        tick_id="t2",
        as_of=now,
        universe=("SOL",),
        symbols={
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=_candidate(symbol="SOL"),
                alert_level="trigger",
            )
        },
    )
    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        equity_scanner=_EmptyFeed(),  # type: ignore[arg-type]
        store=store,
        pipeline=None,
        size_usd=2500.0,
        cortex=_Cortex(mem),
    )
    notes = agent.tick()
    assert any(n.startswith("skip:squeeze_expansion_cap:SOL") for n in notes)
    assert not any(n.startswith("open:SOL:") for n in notes)
