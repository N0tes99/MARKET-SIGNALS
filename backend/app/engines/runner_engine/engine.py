"""Runner Detection Engine — Surface 4 orchestrator."""

from __future__ import annotations

import logging
from uuid import uuid4

from app.engines.runner_engine.compose import (
    aggregate_data_quality,
    collect_explainability,
    compose_runner_scores,
    confidence_from_dimensions,
)
from app.engines.runner_engine.config import RUNNER_PHASE, RunnerConfig, default_runner_config
from app.engines.runner_engine.scoring import score_all_dimensions
from app.engines.runner_engine.stage import classify
from app.engines.runner_engine.types import DataQuality, RunnerCandidate
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)


def _candidate_id(symbol: str) -> str:
    return f"{symbol.lower()}-runner-{uuid4().hex[:8]}"


class RunnerEngine:
    """Evaluate one symbol into an explainable RunnerCandidate.

    Phase 2 scores real structure / optional asymmetry. Does not write grades.
    """

    def __init__(
        self,
        config: RunnerConfig | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        self.config = config or default_runner_config()
        self._market = market_data

    def evaluate(self, symbol: str) -> RunnerCandidate:
        """Score a symbol and classify stage / signal / watchlist."""
        normalized = symbol.upper().strip()
        md = self._market or MarketDataService()
        dimensions, tape = score_all_dimensions(
            normalized, market_data=md, config=self.config
        )
        scores = compose_runner_scores(dimensions, self.config)
        factors, conflicts, risk_flags = collect_explainability(dimensions)
        has_severe = any(
            "dilution" in f.lower() or "going-concern" in f.lower() for f in risk_flags
        )
        fundamentals_available = dimensions["fundamental"].data_quality != "missing"
        stage, signal, watchlist = classify(
            scores,
            self.config,
            has_severe_risk=has_severe,
            fundamentals_available=fundamentals_available,
        )
        quality = aggregate_data_quality(dimensions)
        confidence = confidence_from_dimensions(dimensions)
        qualities: dict[str, DataQuality] = {
            name: dim.data_quality for name, dim in dimensions.items()
        }

        factors = [
            f"Runner Score {scores.runner_score:.1f} (opportunity; structure-only cap)",
            f"Risk Score {scores.risk_score:.1f} (separate; not suppressed)",
            *factors,
        ]

        candidate = RunnerCandidate(
            id=_candidate_id(normalized),
            symbol=normalized,
            stage=stage,
            signal_type=signal,
            watchlist=watchlist,
            scores=scores,
            factors=factors,
            conflicts=conflicts,
            risk_flags=risk_flags,
            confidence=confidence,
            data_quality=quality,
            phase=RUNNER_PHASE,
            qualities=qualities,
            tape=tape,
        )
        logger.info(
            "runner_evaluate symbol=%s runner=%.1f risk=%.1f stage=%s signal=%s "
            "watchlist=%s quality=%s phase=%s",
            normalized,
            scores.runner_score,
            scores.risk_score,
            stage,
            signal,
            watchlist,
            quality,
            RUNNER_PHASE,
        )
        return candidate
