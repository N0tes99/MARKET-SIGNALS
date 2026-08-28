"""Unit tests for Surface 4 Runner Detection (Phase 2 structure)."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from app.core.service_dependencies import get_runner_scanner
from app.engines.runner_engine import (
    DEFAULT_SEED_UNIVERSE,
    RUNNER_PHASE,
    RunnerEngine,
    RunnerScanner,
    default_runner_config,
)
from app.engines.runner_engine.compose import compose_runner_scores
from app.engines.runner_engine.config import AlertThresholds, RunnerConfig, StageThresholds
from app.engines.runner_engine.scoring.edgar import EdgarSnapshot
from app.engines.runner_engine.scoring.structure import score_structure
from app.engines.runner_engine.scoring.stubs import score_all_dimensions
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    YahooRunnerSnapshot,
    empty_yahoo_snapshot,
)
from app.engines.runner_engine.stage import classify, classify_alert_gate, classify_stage
from app.engines.runner_engine.types import DimensionScore, RunnerScores
from app.main import app
from app.market_data.providers.mock import MockMarketDataProvider, generate_trending_ohlcv
from app.market_data.service import MarketDataService
from app.market_data.symbols import TRACKED_SYMBOLS, is_tracked


@pytest.fixture(autouse=True)
def _quiet_yahoo(monkeypatch) -> None:
    """Runner unit tests must not hit live Yahoo or SEC."""
    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.stubs.fetch_yahoo_runner_snapshot",
        lambda symbol: empty_yahoo_snapshot(symbol),
    )
    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.stubs.fetch_edgar_snapshot",
        lambda symbol: EdgarSnapshot(symbol=symbol),
    )


def _mock_md(*, market_cap: float | None = 1_200_000_000.0) -> MarketDataService:
    return MarketDataService(
        provider=MockMarketDataProvider(
            ohlcv=generate_trending_ohlcv(rows=80),
            market_cap=market_cap,
        )
    )


def _missing(name: str, score: float = 50.0) -> DimensionScore:
    return DimensionScore(
        name=name,
        score=score,
        confidence=0.35,
        factors=["stub"],
        conflicts=["Insufficient data"],
        data_quality="missing",
    )


def _good(name: str, score: float) -> DimensionScore:
    return DimensionScore(
        name=name,
        score=score,
        confidence=0.85,
        factors=["live"],
        conflicts=[],
        data_quality="good",
    )


def test_seed_universe_nonempty() -> None:
    assert len(DEFAULT_SEED_UNIVERSE) >= 10
    assert "CRDO" in DEFAULT_SEED_UNIVERSE
    assert "SMCI" in DEFAULT_SEED_UNIVERSE
    assert not is_tracked("CRDO")


def test_structure_scorer_uses_momentum(monkeypatch) -> None:
    md = _mock_md()
    dim, tape = score_structure("CRDO", market_data=md)
    assert dim.data_quality == "good"
    assert 0 <= dim.score <= 100
    assert any("20DMA" in f or "momentum" in f.lower() or "Momentum" in f for f in dim.factors)
    assert tape.ret_20d_pct is not None
    assert tape.relative_volume is not None


def test_empty_yahoo_snapshot_stays_missing() -> None:
    dims, _tape = score_all_dimensions(
        "CRDO",
        market_data=_mock_md(),
        snapshot=empty_yahoo_snapshot("CRDO"),
    )
    assert dims["fundamental"].data_quality == "missing"
    assert dims["catalyst"].data_quality == "missing"
    assert dims["discovery_gap"].data_quality == "missing"
    assert dims["short_squeeze_potential"].data_quality == "missing"
    assert dims["structure"].data_quality == "good"
    assert dims["fundamental"].conflicts == []


def _rich_snapshot() -> YahooRunnerSnapshot:
    return YahooRunnerSnapshot(
        symbol="CRDO",
        fetched_ok=True,
        market_cap=1_200_000_000.0,
        revenue_growth=0.42,
        earnings_quarterly_growth=0.31,
        profit_margins=0.18,
        return_on_equity=0.22,
        trailing_pe=48.0,
        forward_pe=32.0,
        short_percent_of_float=0.08,
        short_ratio=3.2,
        shares_short=8_000_000,
        shares_short_prior=7_200_000,
        held_percent_institutions=0.55,
        held_percent_insiders=0.12,
        number_of_analysts=4,
        sector="Technology",
        industry="Semiconductors",
        earnings_date=date(2026, 8, 20),
    )


def test_yahoo_snapshot_fills_all_dims() -> None:
    dims, _tape = score_all_dimensions(
        "CRDO",
        market_data=_mock_md(),
        snapshot=_rich_snapshot(),
    )
    assert dims["fundamental"].data_quality == "good"
    assert dims["catalyst"].data_quality == "good"
    assert dims["discovery_gap"].data_quality == "good"
    assert dims["theme_bottleneck"].data_quality == "good"
    assert dims["institutional_accum"].data_quality == "good"
    assert dims["short_squeeze_potential"].data_quality == "good"
    assert dims["theme_bottleneck"].score >= 70
    assert all("Insufficient data" not in c for d in dims.values() for c in d.conflicts)


def test_compose_skips_missing_dim_spam() -> None:
    from app.engines.runner_engine.compose import collect_explainability

    dims = {
        "fundamental": _missing("fundamental"),
        "catalyst": _missing("catalyst"),
        "structure": _good("structure", 80.0),
        "asymmetry": _good("asymmetry", 80.0),
        "discovery_gap": _missing("discovery_gap"),
        "theme_bottleneck": _missing("theme_bottleneck"),
        "institutional_accum": _missing("institutional_accum"),
        "short_squeeze_potential": _missing("short_squeeze_potential"),
    }
    factors, conflicts, flags = collect_explainability(dims)
    assert not any("Insufficient data" in item for item in conflicts)
    assert not any(item.startswith("Missing data:") for item in flags)
    assert any("Yahoo incomplete" in item for item in flags)
    assert any("[structure]" in item for item in factors)


def test_compose_ignores_missing_fifties() -> None:
    dims = {
        "fundamental": _missing("fundamental"),
        "catalyst": _missing("catalyst"),
        "structure": _good("structure", 80.0),
        "asymmetry": _missing("asymmetry"),
        "discovery_gap": _missing("discovery_gap"),
        "theme_bottleneck": _missing("theme_bottleneck"),
        "institutional_accum": _missing("institutional_accum"),
        "short_squeeze_potential": _missing("short_squeeze_potential"),
    }
    scores = compose_runner_scores(dims, default_runner_config())
    assert scores.runner_score <= default_runner_config().structure_only_cap
    assert scores.runner_score > 0
    assert scores.risk_score >= 50


def test_compose_all_missing_is_capped_zeroish() -> None:
    dims = {
        name: _missing(name)
        for name in (
            "fundamental",
            "catalyst",
            "structure",
            "asymmetry",
            "discovery_gap",
            "theme_bottleneck",
            "institutional_accum",
            "short_squeeze_potential",
        )
    }
    scores = compose_runner_scores(dims, default_runner_config())
    assert scores.runner_score == 0.0
    assert scores.risk_score >= 50


def test_structure_only_cannot_reach_ignition() -> None:
    scores = RunnerScores(fundamental=50, catalyst=50, structure=90, discovery_gap=50)
    stage, signal, watchlist = classify(
        scores, default_runner_config(), fundamentals_available=False
    )
    assert stage in {"dormant", "early_accumulation"}
    assert stage != "ignition"
    assert watchlist in {"early", "none"}
    assert watchlist != "ignition"
    assert watchlist != "running"


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


def test_classify_with_fundamentals_can_reach_ignition() -> None:
    scores = RunnerScores(fundamental=70, catalyst=70, structure=75, discovery_gap=65)
    stage, signal, watchlist = classify(
        scores, default_runner_config(), fundamentals_available=True
    )
    assert stage == "ignition"
    assert signal == "ignition"
    assert watchlist == "ignition"


def test_classify_alert_gate_high_early_none() -> None:
    alerts = AlertThresholds()
    high = RunnerScores(
        fundamental=80,
        catalyst=80,
        structure=80,
        discovery_gap=50,
        runner_score=90,
        risk_score=40,
    )
    assert classify_alert_gate(high, "ignition", alerts) == "high"
    assert classify_alert_gate(high, "running", alerts) == "high"
    assert classify_alert_gate(high, "early", alerts) == "none"

    early = RunnerScores(
        fundamental=80,
        catalyst=40,
        structure=55,
        discovery_gap=75,
        runner_score=60,
        risk_score=40,
    )
    assert classify_alert_gate(early, "early", alerts) == "early"
    assert classify_alert_gate(early, "ignition", alerts) == "none"

    risky = RunnerScores(
        fundamental=80,
        catalyst=80,
        structure=80,
        discovery_gap=50,
        runner_score=90,
        risk_score=80,
    )
    assert classify_alert_gate(risky, "ignition", alerts) == "none"


def test_classify_watchlist_early_for_inflection() -> None:
    scores = RunnerScores(fundamental=75, catalyst=40, structure=40, discovery_gap=80)
    stage, signal, watchlist = classify(
        scores, default_runner_config(), fundamentals_available=True
    )
    assert stage == "fundamental_inflection"
    assert signal == "early_runner"
    assert watchlist == "early"


def test_engine_evaluate_without_yahoo() -> None:
    engine = RunnerEngine(market_data=_mock_md())
    candidate = engine.evaluate("crdo")
    assert candidate.symbol == "CRDO"
    assert candidate.instrument_type == "runner"
    assert candidate.phase == RUNNER_PHASE
    assert candidate.qualities["fundamental"] == "missing"
    assert candidate.qualities["structure"] == "good"
    assert candidate.scores.runner_score <= default_runner_config().structure_only_cap
    assert candidate.stage in {"dormant", "early_accumulation"}
    assert candidate.alert_gate == "none"
    assert any("Runner Score" in f for f in candidate.factors)
    assert not any("Insufficient data" in c for c in candidate.conflicts)
    assert not any(f.startswith("Missing data:") for f in candidate.risk_flags)


def test_engine_evaluate_with_yahoo_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.stubs.fetch_yahoo_runner_snapshot",
        lambda symbol: _rich_snapshot(),
    )
    engine = RunnerEngine(market_data=_mock_md())
    candidate = engine.evaluate("CRDO")
    assert candidate.qualities["fundamental"] == "good"
    assert candidate.qualities["short_squeeze_potential"] == "good"
    assert candidate.scores.runner_score > 0
    assert candidate.alert_gate in {"none", "early", "high"}
    assert not any("Insufficient data" in c for c in candidate.conflicts)


def test_scanner_with_yahoo_may_fill_ignition(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.stubs.fetch_yahoo_runner_snapshot",
        lambda symbol: _rich_snapshot(),
    )
    cfg = RunnerConfig(seed_universe=("CRDO",))
    scanner = RunnerScanner(config=cfg, market_data=_mock_md())
    results = scanner.scan(use_cache=False)
    assert len(results) == 1
    assert results[0].qualities["fundamental"] == "good"
    assert results[0].scores.runner_score > default_runner_config().structure_only_cap
    lists = scanner.lists()
    assert set(lists) == {"early", "ignition", "running"}


def test_scanner_covers_seed_universe() -> None:
    cfg = RunnerConfig(seed_universe=("CRDO", "ALAB", "VRT"))
    scanner = RunnerScanner(config=cfg, market_data=_mock_md())
    results = scanner.scan(use_cache=False)
    assert len(results) == 3
    assert {c.symbol for c in results} == {"CRDO", "ALAB", "VRT"}
    lists = scanner.lists()
    assert set(lists) == {"early", "ignition", "running"}
    assert lists["ignition"] == []
    assert lists["running"] == []


@pytest.mark.asyncio
async def test_runners_api_feed_and_detail(client: AsyncClient) -> None:
    cfg = RunnerConfig(seed_universe=("CRDO", "SMCI"))
    scanner = RunnerScanner(config=cfg, market_data=_mock_md())
    app.dependency_overrides[get_runner_scanner] = lambda: scanner

    feed = await client.get("/api/v1/runners")
    assert feed.status_code == 200
    body = feed.json()
    assert body["symbols_scanned"] == 2
    assert "fundamentals_filled" in body
    assert "fundamentals_missing" in body
    assert body["fundamentals_filled"] + body["fundamentals_missing"] == 2
    assert len(body["candidates"]) == 2
    first = body["candidates"][0]
    assert first["phase"] == RUNNER_PHASE
    assert first["alert_gate"] in {"none", "early", "high"}
    assert first["qualities"]["structure"] == "good"
    assert first["scores"]["runner_score"] <= 62.0

    detail = await client.get("/api/v1/runners/CRDO")
    assert detail.status_code == 200
    cand = detail.json()["candidate"]
    assert cand["symbol"] == "CRDO"
    assert cand["stage"] in {"dormant", "early_accumulation"}

    meta = await client.get("/api/v1/runners/meta/config")
    assert meta.status_code == 200
    assert meta.json()["phase"] == RUNNER_PHASE
    assert "CRDO" in meta.json()["seed_universe"]

    lists = await client.get("/api/v1/runners/lists")
    assert lists.status_code == 200
    assert lists.json()["ignition"] == []
    assert lists.json()["running"] == []
    assert "fundamentals_filled" in lists.json()

    app.dependency_overrides.pop(get_runner_scanner, None)


@pytest.mark.asyncio
async def test_runners_api_does_not_require_surface1_tracked(client: AsyncClient) -> None:
    """Ad-hoc symbols are allowed — Surface 4 has its own universe."""
    cfg = RunnerConfig(seed_universe=("ZZZZ",))
    scanner = RunnerScanner(config=cfg, market_data=_mock_md())
    app.dependency_overrides[get_runner_scanner] = lambda: scanner
    resp = await client.get("/api/v1/runners/ZZZZ")
    assert resp.status_code == 200
    assert resp.json()["candidate"]["symbol"] == "ZZZZ"
    app.dependency_overrides.pop(get_runner_scanner, None)


@pytest.mark.asyncio
async def test_assets_list_excludes_untracked_runner_seed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/assets?sync=true")
    assert response.status_code == 200
    symbols = {row["symbol"] for row in response.json()["assets"]}
    assert "CRDO" not in symbols
    assert symbols == set(TRACKED_SYMBOLS)
