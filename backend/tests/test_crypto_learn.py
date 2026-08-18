"""Futures coefficient tuner — paper_honest perp_momentum only."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.engines.learning_engine import LearningEngine, SignalOutcome
from app.engines.learning_engine.store import InMemorySignalStore
from app.engines.runner_engine.crypto_learn import (
    DEFAULT_COEFFICIENTS,
    encode_paper_open_notes,
    get_crypto_learn_coefficients,
    get_crypto_learn_config,
    maybe_retune_from_paper,
    parse_paper_notes,
    tune_coefficients,
)


@pytest.fixture(autouse=True)
def _reset_coeffs() -> None:
    get_crypto_learn_config().reset(persist=False)
    yield
    get_crypto_learn_config().reset(persist=False)


def _open(
    engine: LearningEngine,
    *,
    setup: str = "perp_momentum",
    bucket: str = "running",
    funding: float = 2.0,
    confidence: float = 70.0,
) -> None:
    engine.record_paper_open(
        paper_trade_id=uuid4(),
        symbol="BTC",
        setup_type=setup,
        direction="long",
        confidence=confidence,
        opportunity_score=confidence,
        entry_price=100.0,
        extras={
            "radar_bucket": bucket,
            "radar_score": 70.0,
            "funding_bps": funding,
            "mom_12h_pct": 5.0,
            "basis_pct": 0.1,
        },
    )


def _resolve_all(engine: LearningEngine, outcome: str, ret: float) -> None:
    for rec in engine.list_paper_memory(limit=500):
        if rec.outcome is None and rec.paper_trade_id is not None:
            engine.resolve_paper_close(
                paper_trade_id=rec.paper_trade_id,
                outcome=outcome,
                realized_return_pct=ret,
            )


def test_encode_parse_paper_notes_roundtrip() -> None:
    notes = encode_paper_open_notes(
        setup_type="perp_momentum",
        direction="short",
        factors=["12h +4.0%"],
        extras={
            "radar_bucket": "crowded",
            "radar_score": 66.5,
            "funding_bps": 12.0,
            "mom_12h_pct": 1.2,
            "basis_pct": 0.15,
        },
    )
    parsed = parse_paper_notes(notes)
    assert parsed["setup"] == "perp_momentum"
    assert parsed["radar_bucket"] == "crowded"
    assert parsed["funding_bps"] == pytest.approx(12.0)
    assert parsed["basis_pct"] == pytest.approx(0.15)


def test_outcome_stats_by_setup_filters_perp_momentum() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    _open(engine, setup="perp_momentum", bucket="running")
    _open(engine, setup="funding_extreme", bucket="watch")
    _resolve_all(engine, SignalOutcome.WIN.value, 2.0)

    perp = engine.outcome_stats_by_setup("perp_momentum")
    other = engine.outcome_stats_by_setup("funding_extreme")
    assert perp["resolved"] == 1
    assert perp["wins"] == 1
    assert perp["win_rate"] == 100.0
    assert other["resolved"] == 1
    assert engine.outcome_stats_by_setup("missing_setup")["resolved"] == 0


def test_tuner_skips_apply_when_n_below_ten() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    for _ in range(6):
        _open(engine, bucket="crowded", funding=12.0)
    _resolve_all(engine, SignalOutcome.LOSS.value, -3.0)

    rows = [r for r in engine.list_paper_memory() if r.outcome]
    assert tune_coefficients(rows) is None
    assert maybe_retune_from_paper(engine) is None
    assert get_crypto_learn_coefficients().preset == "default"


def test_tuner_picks_skip_crowded_when_crowded_loses() -> None:
    engine = LearningEngine(store=InMemorySignalStore())
    for _ in range(6):
        _open(engine, bucket="crowded", funding=12.0, confidence=68.0)
    _resolve_all(engine, SignalOutcome.LOSS.value, -4.0)
    for _ in range(6):
        _open(engine, bucket="running", funding=1.0, confidence=72.0)
    for rec in engine.list_paper_memory(limit=500):
        if rec.outcome is None and rec.paper_trade_id is not None:
            parsed = parse_paper_notes(rec.notes)
            if parsed.get("radar_bucket") == "running":
                engine.resolve_paper_close(
                    paper_trade_id=rec.paper_trade_id,
                    outcome=SignalOutcome.WIN.value,
                    realized_return_pct=3.0,
                )

    rows = [r for r in engine.list_paper_memory() if r.outcome]
    winner = tune_coefficients(rows)
    assert winner is not None
    assert winner.skip_crowded_opens is True

    applied = maybe_retune_from_paper(engine)
    assert applied is not None
    live = get_crypto_learn_coefficients()
    assert live.skip_crowded_opens is True
    assert live.preset.startswith("learned_paper")
    assert live != DEFAULT_COEFFICIENTS
