"""Semantic consolidation from episodic cortex ticks."""

from datetime import UTC, datetime, timedelta

from app.cortex.types import SymbolContext, WorkingMemory
from app.engines.expansion_engine.types import (
    CompressionResult,
    ExpansionCandidate,
    ExpansionState,
    SqueezeFuelResult,
    TriggerResult,
)
from app.memory.episodic.store import InMemoryEpisodicStore
from app.memory.semantic.calibration import calibration_hit_rate
from app.memory.semantic.consolidator import consolidate_from_episodic
from app.memory.semantic.lead_time import median_lead_time_hours
from app.memory.semantic.store import InMemorySemanticStore


def _expansion(
    symbol: str,
    state: ExpansionState,
    net: float,
    as_of: datetime,
) -> ExpansionCandidate:
    return ExpansionCandidate(
        id=f"{symbol}-{state.value}",
        symbol=symbol,
        state=state,
        direction_bias="up",
        up_score=net,
        down_score=20.0,
        net_score=net,
        confidence="medium",
        setup_level="high",
        trigger_active=state in {ExpansionState.TRIGGERING, ExpansionState.EXPANDING},
        horizon="1h–12h",
        invalidation="test",
        key_trigger="test",
        compression=CompressionResult(
            score=88.0,
            atr_percentile=5.0,
            bb_width_percentile=8.0,
            range_compression_pct=90.0,
            volume_compression_pct=70.0,
            factors=["compressed"],
        ),
        squeeze=SqueezeFuelResult(score=70.0, direction="up", factors=["fuel"]),
        trigger=TriggerResult(
            active=state == ExpansionState.TRIGGERING,
            direction="up",
            volume_ratio=2.0,
            breakout_level=None,
        ),
        as_of=as_of,
    )


def _memory(tick: str, as_of: datetime, state: ExpansionState, net: float) -> WorkingMemory:
    exp = _expansion("SOL", state, net, as_of)
    return WorkingMemory(
        tick_id=tick,
        as_of=as_of,
        universe=("SOL",),
        symbols={
            "SOL": SymbolContext(
                symbol="SOL",
                expansion=exp,
                alert_level="primed" if state == ExpansionState.PRIMED else "trigger",
            )
        },
        phase="cortex_v2",
    )


def test_consolidate_lead_time_and_calibration() -> None:
    episodic = InMemoryEpisodicStore()
    semantic = InMemorySemanticStore()
    t0 = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(hours=3)
    episodic.append(_memory("a", t0, ExpansionState.PRIMED, 82.0))
    episodic.append(_memory("b", t1, ExpansionState.TRIGGERING, 88.0))

    stats = consolidate_from_episodic(episodic, semantic)
    assert stats
    lead = median_lead_time_hours(store=semantic)
    assert lead == 3.0
    hit = calibration_hit_rate(80, store=semantic)
    assert hit == 1.0


def test_calibration_miss_when_primed_goes_dormant() -> None:
    episodic = InMemoryEpisodicStore()
    semantic = InMemorySemanticStore()
    t0 = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
    t1 = t0 + timedelta(hours=1)
    episodic.append(_memory("a", t0, ExpansionState.PRIMED, 71.0))
    episodic.append(_memory("b", t1, ExpansionState.DORMANT, 20.0))

    consolidate_from_episodic(episodic, semantic)
    hit = calibration_hit_rate(70, store=semantic)
    assert hit == 0.0
    assert median_lead_time_hours(store=semantic) is None
