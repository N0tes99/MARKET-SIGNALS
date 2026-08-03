"""Execution Engine — determines entry timing."""

from dataclasses import dataclass
from enum import StrEnum

from app.engines.evidence_engine.types import EvidenceBundle
from app.engines.opportunity_engine.engine import OpportunityResult
from app.utils.scoring_helpers import clamp_score


class ExecutionSignal(StrEnum):
    """Entry timing recommendation."""

    WAIT = "WAIT"
    WATCH = "WATCH"
    EXECUTE = "EXECUTE"


@dataclass
class ExecutionResult:
    """Execution timing output for a single asset."""

    symbol: str
    signal: ExecutionSignal
    confidence: float
    description: str


def _category_score(evidence: EvidenceBundle, category: str) -> float:
    """Extract score for a scoring category."""
    for item in evidence.items:
        if item.category == category:
            return item.score
    return 0.0


class ExecutionEngine:
    """Determines optimal entry timing based on accumulated evidence."""

    EXECUTE_MIN_CONFIDENCE = 70.0
    WATCH_MIN_CONFIDENCE = 50.0

    def evaluate(
        self,
        symbol: str,
        evidence: EvidenceBundle,
        opportunity: OpportunityResult,
    ) -> ExecutionResult:
        """Evaluate entry timing for an asset."""
        confidence = evidence.total_confidence
        trend = _category_score(evidence, "Trend")
        momentum = _category_score(evidence, "Momentum")
        risk = _category_score(evidence, "Risk")
        volume = _category_score(evidence, "Volume")

        if (
            confidence >= self.EXECUTE_MIN_CONFIDENCE
            and trend >= 60
            and momentum >= 45
            and risk >= 40
            and volume >= 40
        ):
            signal = ExecutionSignal.EXECUTE
            description = (
                f"{symbol}: Entry conditions met — trend {trend:.0f}, "
                f"momentum {momentum:.0f}, risk {risk:.0f}"
            )
        elif confidence >= self.WATCH_MIN_CONFIDENCE:
            signal = ExecutionSignal.WATCH
            description = (
                f"{symbol}: Monitor for entry — confidence {confidence:.0f}%, "
                f"awaiting alignment"
            )
        else:
            signal = ExecutionSignal.WAIT
            description = f"{symbol}: No entry — confidence {confidence:.0f}% too low"

        timing_confidence = clamp_score(
            (confidence * 0.4) + (trend * 0.25) + (momentum * 0.2) + (risk * 0.15)
        )

        return ExecutionResult(
            symbol=symbol.upper(),
            signal=signal,
            confidence=timing_confidence,
            description=description,
        )
