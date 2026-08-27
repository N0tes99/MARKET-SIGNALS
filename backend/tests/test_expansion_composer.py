"""Named expansion scoring composer — normalize, provenance, direction."""

from app.engines.expansion_engine.config import ExpansionConfig, expansion_config_from_dict
from app.engines.expansion_engine.scoring.composer import compose_scores
from app.engines.expansion_engine.scoring.weights import ExpansionWeights, weights_from_config
from app.engines.expansion_engine.types import (
    CompressionResult,
    ExpansionState,
    SqueezeFuelResult,
    TriggerResult,
)
from app.memory.procedural.config_store import reset_process_overlay, save_expansion_config


def setup_function() -> None:
    reset_process_overlay()


def teardown_function() -> None:
    reset_process_overlay()


def _compression(score: float = 80.0) -> CompressionResult:
    return CompressionResult(
        score=score,
        atr_percentile=10.0,
        bb_width_percentile=10.0,
        range_compression_pct=80.0,
        volume_compression_pct=70.0,
        factors=[],
    )


def _squeeze(*, score: float = 70.0, direction: str = "up") -> SqueezeFuelResult:
    return SqueezeFuelResult(score=score, direction=direction, factors=[], conflicts=["oi unknown"])


def _trigger(*, active: bool = True, direction: str = "up") -> TriggerResult:
    return TriggerResult(
        active=active,
        direction=direction,
        volume_ratio=2.0,
        breakout_level=100.0,
    )


def test_normalize_uneven_weights() -> None:
    raw = ExpansionWeights(
        compression=1.0,
        squeeze=3.0,
        trigger=0.0,
        momentum=0.0,
        derivatives=0.0,
    )
    w = raw.normalize()
    assert w.normalized is True
    assert w.compression + w.squeeze + w.trigger + w.momentum + w.derivatives == 1.0
    assert w.compression == 0.25
    assert w.squeeze == 0.75
    assert w.trigger == 0.0


def test_normalize_zero_weights_falls_back() -> None:
    w = ExpansionWeights(
        compression=0.0,
        squeeze=0.0,
        trigger=0.0,
        momentum=0.0,
        derivatives=0.0,
        source="dead",
        version=4,
    ).normalize()
    assert w.source == "dead"
    assert w.version == 4
    assert w.compression == 0.25
    assert w.squeeze == 0.25
    assert w.trigger == 0.20
    assert w.momentum == 0.15
    assert w.derivatives == 0.15
    assert sum(w.as_dict().values()) == 1.0


def test_weights_from_config_reads_memory_policy() -> None:
    mutated = expansion_config_from_dict(
        {
            "weight_compression": 0.9,
            "weight_squeeze": 0.1,
            "weight_trigger": 0.0,
            "weight_momentum": 0.0,
            "weight_derivatives": 0.0,
        }
    )
    save_expansion_config(mutated)
    w = weights_from_config()
    assert w.source == "memory"
    assert w.version >= 1
    assert w.normalized is True
    assert w.compression == 0.9
    assert w.squeeze == 0.1


def test_compose_logs_policy_contributor() -> None:
    pinned = ExpansionWeights(
        compression=0.25,
        squeeze=0.25,
        trigger=0.20,
        momentum=0.15,
        derivatives=0.15,
        source="pin",
        version=7,
    )
    _up, _down, contributors, _conflicts = compose_scores(
        compression=_compression(),
        squeeze=_squeeze(),
        trigger=_trigger(),
        mom_12h_pct=2.0,
        funding_bps=4.0,
        state=ExpansionState.TRIGGERING,
        weights=pinned,
    )
    policy = contributors[0]
    assert policy.label == "Policy"
    assert policy.points == 0.0
    assert "pin v7" in policy.detail
    assert "w=" in policy.detail


def test_compose_pinned_weights_is_directional_up() -> None:
    pinned = ExpansionWeights(
        compression=0.2,
        squeeze=0.3,
        trigger=0.3,
        momentum=0.1,
        derivatives=0.1,
        source="test",
        version=1,
    )
    up, down, contributors, conflicts = compose_scores(
        compression=_compression(88.0),
        squeeze=_squeeze(score=80.0, direction="up"),
        trigger=_trigger(active=True, direction="up"),
        mom_12h_pct=3.0,
        funding_bps=5.0,
        state=ExpansionState.TRIGGERING,
        weights=pinned,
    )
    assert up > down
    assert up >= 70.0
    labels = {c.label for c in contributors}
    assert "Squeeze fuel" in labels
    assert "Trigger" in labels
    assert "No active breakout trigger" not in conflicts


def test_compose_pinned_weights_is_directional_down() -> None:
    pinned = ExpansionWeights(
        compression=0.2,
        squeeze=0.3,
        trigger=0.3,
        momentum=0.1,
        derivatives=0.1,
        source="test",
        version=1,
    )
    up, down, contributors, _conflicts = compose_scores(
        compression=_compression(88.0),
        squeeze=_squeeze(score=80.0, direction="down"),
        trigger=_trigger(active=True, direction="down"),
        mom_12h_pct=-3.0,
        funding_bps=-5.0,
        state=ExpansionState.TRIGGERING,
        weights=pinned,
    )
    assert down > up
    squeeze = next(c for c in contributors if c.label == "Squeeze fuel")
    assert squeeze.detail == "downside"


def test_heavier_squeeze_weight_moves_the_score() -> None:
    light = ExpansionWeights(
        compression=0.5,
        squeeze=0.1,
        trigger=0.2,
        momentum=0.1,
        derivatives=0.1,
        source="test",
        version=1,
    )
    heavy = ExpansionWeights(
        compression=0.1,
        squeeze=0.5,
        trigger=0.2,
        momentum=0.1,
        derivatives=0.1,
        source="test",
        version=1,
    )
    kwargs = {
        "compression": _compression(50.0),
        "squeeze": _squeeze(score=100.0, direction="up"),
        "trigger": _trigger(active=False, direction="neutral"),
        "mom_12h_pct": None,
        "funding_bps": None,
        "state": ExpansionState.PRIMED,
        "config": ExpansionConfig(),
    }
    up_light, _, _, _ = compose_scores(**kwargs, weights=light)
    up_heavy, _, _, _ = compose_scores(**kwargs, weights=heavy)
    assert up_heavy > up_light
