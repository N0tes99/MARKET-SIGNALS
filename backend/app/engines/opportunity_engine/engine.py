"""Opportunity Engine — ranks every asset."""

from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceBundle
from app.scoring.grading import TradeState, compute_expected_value, score_to_grade
from app.utils.scoring_helpers import clamp_score


@dataclass
class OpportunityResult:
    """Opportunity ranking output for a single asset."""

    symbol: str
    opportunity_score: float
    trade_grade: str
    expected_value: float
    trade_state: TradeState
    description: str


class OpportunityEngine:
    """Ranks assets by composite opportunity score from evidence."""

    WATCH_THRESHOLD = 50.0
    EXECUTE_THRESHOLD = 70.0

    def evaluate(
        self,
        symbol: str,
        evidence: EvidenceBundle,
        risk_reward_ratio: float = 1.5,
    ) -> OpportunityResult:
        """Rank a single asset from its evidence bundle."""
        score = evidence.total_confidence
        grade = score_to_grade(score)
        expected_value = compute_expected_value(score, risk_reward_ratio)

        if score < self.WATCH_THRESHOLD:
            state = TradeState.IGNORE
            description = f"{symbol}: Below watch threshold ({score:.0f}%)"
        elif score < self.EXECUTE_THRESHOLD:
            state = TradeState.WATCH
            description = f"{symbol}: Building evidence ({score:.0f}%), grade {grade}"
        else:
            state = TradeState.WATCH  # upgraded to EXECUTE by pipeline if timing aligns
            description = f"{symbol}: Strong opportunity ({score:.0f}%), grade {grade}"

        return OpportunityResult(
            symbol=symbol.upper(),
            opportunity_score=clamp_score(score),
            trade_grade=grade,
            expected_value=expected_value,
            trade_state=state,
            description=description,
        )

    def rank(
        self,
        results: list[OpportunityResult],
    ) -> list[OpportunityResult]:
        """Sort opportunities by score descending."""
        return sorted(results, key=lambda r: r.opportunity_score, reverse=True)
