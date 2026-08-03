"""Derivatives Engine — derivatives market analysis."""

import logging
from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)


@dataclass
class DerivativesResult:
    """Derivatives analysis output."""

    symbol: str
    funding_rate: float | None
    open_interest: float | None
    score: float
    description: str


class DerivativesEngine:
    """Analyzes funding rate and open interest."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str) -> DerivativesResult | None:
        """Analyze derivatives positioning for an asset."""
        try:
            snapshot = self._market_data.get_derivatives(symbol)
        except Exception:
            logger.exception("Failed to fetch derivatives for %s", symbol)
            return None

        funding = snapshot.funding_rate
        score = 50.0
        description = f"{symbol}: Derivatives data unavailable"

        if funding is not None:
            # Normalize funding: extreme positive = crowded longs (caution)
            # Score peaks when funding is near neutral
            funding_bps = funding * 10_000
            score = clamp_score(70 - abs(funding_bps) * 5)
            bias = "elevated long funding" if funding > 0.0005 else "neutral funding"
            if funding < -0.0005:
                bias = "negative funding (shorts paying)"
            description = (
                f"{symbol}: Funding {funding_bps:.2f} bps, OI "
                f"{snapshot.open_interest:,.0f} — {bias}"
            )

        return DerivativesResult(
            symbol=symbol.upper(),
            funding_rate=funding,
            open_interest=snapshot.open_interest,
            score=score,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return derivatives evidence item."""
        del timeframe  # Derivatives are not timeframe-specific
        result = self.analyze(symbol)
        if result is None:
            return [
                EvidenceItem(
                    source="derivatives_engine",
                    category=ScoringCategory.DERIVATIVES.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.DERIVATIVES],
                    description=f"{symbol}: Derivatives data unavailable",
                ),
            ]

        return [
            EvidenceItem(
                source="derivatives_engine",
                category=ScoringCategory.DERIVATIVES.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.DERIVATIVES],
                description=result.description,
            ),
        ]
