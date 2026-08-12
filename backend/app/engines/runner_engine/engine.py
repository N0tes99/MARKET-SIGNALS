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
from app.engines.runner_engine.config import RunnerConfig, default_runner_config
from app.engines.runner_engine.scoring import score_all_dimensions
from app.engines.runner_engine.stage import classify
from app.engines.runner_engine.types import RunnerCandidate

logger = logging.getLogger(__name__)


def _candidate_id(symbol: str) -> str:
    return f"{symbol.lower()}-runner-{uuid4().hex[:8]}"


class RunnerEngine:
    """Evaluate one symbol into an explainable RunnerCandidate.

    Phase 1 uses stub dimension scorers. Does not write into Evidence grades.
    """

    def __init__(self, config: RunnerConfig | None = None) -> None:
        self.config = config or default_runner_config()

    def evaluate(self, symbol: str) -> RunnerCandidate:
        """Score a symbol and classify stage / signal / watchlist."""
        normalized = symbol.upper().strip()
        dimensions = score_all_dimensions(normalized)
        scores = compose_runner_scores(dimensions, self.config)
        factors, conflicts, risk_flags = collect_explainability(dimensions)
        has_severe = any(
            "dilution" in f.lower() or "going-concern" in f.lower() for f in risk_flags
        )
        stage, signal, watchlist = classify(
            scores, self.config, has_severe_risk=has_severe
        )
        quality = aggregate_data_quality(dimensions)
        confidence = confidence_from_dimensions(dimensions)

        # Always surface opportunity vs risk separation in factors
        factors = [
            f"Runner Score {scores.runner_score:.1f} (opportunity)",
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
            phase="1_stub",
        )
        logger.info(
            "runner_evaluate symbol=%s runner=%.1f risk=%.1f stage=%s signal=%s "
            "watchlist=%s quality=%s",
            normalized,
            scores.runner_score,
            scores.risk_score,
            stage,
            signal,
            watchlist,
            quality,
        )
        return candidate
