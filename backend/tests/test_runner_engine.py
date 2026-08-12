"""Unit tests for Surface 4 Runner Detection (Phase 1 stub)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.service_dependencies import get_runner_scanner
from app.engines.runner_engine import (
    DEFAULT_SEED_UNIVERSE,
    RunnerEngine,
    RunnerScanner,
    default_runner_config,
)
from app.engines.runner_engine.compose import compose_runner_scores
from app.engines.runner_engine.config import RunnerConfig, StageThresholds
from app.engines.runner_engine.scoring.stubs import score_all_dimensions
from app.engines.runner_engine.stage import classify, classify_stage
from app.engines.runner_engine.types import RunnerScores
from app.main import app


def test_seed_universe_nonempty() -> None:
    assert len(DEFAULT_SEED_UNIVERSE) >= 10
    assert "CRDO" in DEFAULT_SEED_UNIVERSE
    assert "SMCI" in DEFAULT_SEED_UNIVERSE


def test_stub_dimensions_mark_missing_data() -> None:
    dims = score_all_dimensions("CRDO")
    assert set(dims) >= {
        "fundamental",
        "catalyst",
        "structure",
        "asymmetry",
        "discovery_gap",
    }
    for dim in dims.values():
        assert dim.data_quality == "missing"
        assert 0 <= dim.score <= 100
        assert dim.factors


def test_compose_keeps_opportunity_and_risk_separate() -> None:
    dims = score_all_dimensions("VRT")
    scores = compose_runner_scores(dims, default_runner_config())
    assert 0 <= scores.runner_score <= 100
    assert 0 <= scores.risk_score <= 100
    # Missing data should elevate risk above a "clean data" baseline
    assert scores.risk_score >= 50


def test_stage_classifier_prioritizes_inflection_to_ignition() -> None:
    thresholds = StageThresholds()
    dormant = RunnerScores(fundamental=40, catalyst=40, structure=40, discovery_gap=50)
    assert classify_stage(dormant, thresholds) == "dormant"

    inflection = RunnerScores(fundamental=70, catalyst=40, structure=40, discovery_gap=70)
    assert classify_stage(inflection, thresholds) == "fundamental_inflection"

    accumulation = RunnerScores(fundamental=70, catalyst=40, structure=60, discovery_gap=70)
    assert classify_stage(accumulation, thresholds) == "early_accumulation"

    catalyst = RunnerScores(fundamental=70, catalyst=70, structure=50, discovery_gap=70)
    assert classify_stage(catalyst, thresholds) == "catalyst"

    ignition = RunnerScores(fundamental=70, catalyst=70, structure=75, discovery_gap=65)
    assert classify_stage(ignition, thresholds) == "ignition"

    extended = RunnerScores(fundamental=70, catalyst=70, structure=90, discovery_gap=20)
    assert classify_stage(extended, thresholds) == "extended"


def test_classify_watchlist_early_for_inflection() -> None:
    scores = RunnerScores(fundamental=75, catalyst=40, structure=40, discovery_gap=80)
    stage, signal, watchlist = classify(scores, default_runner_config())
    assert stage == "fundamental_inflection"
    assert signal == "early_runner"
    assert watchlist == "early"


def test_engine_evaluate_returns_explainable_candidate() -> None:
    engine = RunnerEngine()
    candidate = engine.evaluate("crdo")
    assert candidate.symbol == "CRDO"
    assert candidate.instrument_type == "runner"
    assert candidate.phase == "1_stub"
    assert candidate.data_quality == "missing"
    assert candidate.scores.runner_score >= 0
    assert candidate.scores.risk_score >= 0
    assert any("Runner Score" in f for f in candidate.factors)
    assert any("Risk Score" in f for f in candidate.factors)
    assert candidate.risk_flags  # missing-data flags
    assert candidate.conflicts


def test_scanner_covers_seed_universe() -> None:
    # Tiny universe for speed
    cfg = RunnerConfig(seed_universe=("CRDO", "ALAB", "VRT"))
    scanner = RunnerScanner(config=cfg)
    results = scanner.scan(use_cache=False)
    assert len(results) == 3
    assert {c.symbol for c in results} == {"CRDO", "ALAB", "VRT"}
    lists = scanner.lists()
    assert set(lists) == {"early", "ignition", "running"}


@pytest.mark.asyncio
async def test_runners_api_feed_and_detail(client: AsyncClient) -> None:
    # Inject a tiny scanner so the feed stays fast
    cfg = RunnerConfig(seed_universe=("CRDO", "SMCI"))
    scanner = RunnerScanner(config=cfg)
    app.dependency_overrides[get_runner_scanner] = lambda: scanner

    feed = await client.get("/api/v1/runners")
    assert feed.status_code == 200
    body = feed.json()
    assert body["symbols_scanned"] == 2
    assert len(body["candidates"]) == 2
    first = body["candidates"][0]
    assert "scores" in first
    assert "runner_score" in first["scores"]
    assert "risk_score" in first["scores"]
    assert first["factors"]
    assert first["data_quality"] == "missing"

    detail = await client.get("/api/v1/runners/CRDO")
    assert detail.status_code == 200
    cand = detail.json()["candidate"]
    assert cand["symbol"] == "CRDO"
    assert cand["stage"] in {
        "dormant",
        "fundamental_inflection",
        "early_accumulation",
        "catalyst",
        "ignition",
        "discovery",
        "momentum",
        "extended",
    }

    meta = await client.get("/api/v1/runners/meta/config")
    assert meta.status_code == 200
    assert "CRDO" in meta.json()["seed_universe"]

    lists = await client.get("/api/v1/runners/lists")
    assert lists.status_code == 200
    assert "early" in lists.json()

    app.dependency_overrides.pop(get_runner_scanner, None)


@pytest.mark.asyncio
async def test_runners_api_does_not_require_surface1_tracked(client: AsyncClient) -> None:
    """Ad-hoc symbols are allowed — Surface 4 has its own universe."""
    resp = await client.get("/api/v1/runners/ZZZZ")
    assert resp.status_code == 200
    assert resp.json()["candidate"]["symbol"] == "ZZZZ"
