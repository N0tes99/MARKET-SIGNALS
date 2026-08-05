"""Derivatives Engine — funding level, trend, and OI change."""

import logging
from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.providers.bybit_derivatives import (
    fetch_derivatives_depth,
    oi_change_pct,
    score_derivatives_composite,
)
from app.market_data.service import MarketDataService
from app.market_data.symbols import AssetClass, get_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory

logger = logging.getLogger(__name__)


@dataclass
class DerivativesResult:
    """Derivatives analysis output."""

    symbol: str
    funding_rate: float | None
    open_interest: float | None
    score: float
    description: str
    source: str = ""


class DerivativesEngine:
    """Analyzes funding rate trend and open-interest change (crowded vs empty)."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service (kept for DI compatibility)."""
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str) -> DerivativesResult | None:
        """Analyze derivatives positioning for an asset."""
        normalized = symbol.upper()
        try:
            asset_class = get_asset_class(normalized)
        except ValueError:
            asset_class = None

        if asset_class is not None and asset_class != AssetClass.CRYPTO:
            return DerivativesResult(
                symbol=normalized,
                funding_rate=None,
                open_interest=None,
                score=50.0,
                description=f"{normalized}: Derivatives N/A for {asset_class.value}",
                source="",
            )

        depth = fetch_derivatives_depth(normalized)
        if depth is None or depth.funding_rate is None:
            # Legacy snapshot path (mock / tests)
            try:
                snapshot = self._market_data.get_derivatives(normalized)
            except Exception:
                logger.exception("Failed to fetch derivatives for %s", normalized)
                return None
            if snapshot.funding_rate is None:
                return DerivativesResult(
                    symbol=normalized,
                    funding_rate=None,
                    open_interest=None,
                    score=50.0,
                    description=f"{normalized}: Derivatives data unavailable",
                    source="",
                )
            score, desc = score_derivatives_composite(
                snapshot.funding_rate,
                [],
                None,
            )
            if snapshot.open_interest is not None:
                desc = (
                    f"{normalized}: {desc}; OI {snapshot.open_interest:,.0f}"
                )
            else:
                desc = f"{normalized}: {desc}"
            return DerivativesResult(
                symbol=normalized,
                funding_rate=snapshot.funding_rate,
                open_interest=snapshot.open_interest,
                score=score,
                description=desc,
                source="snapshot",
            )

        oi_delta = oi_change_pct(depth.oi_history)
        score, desc = score_derivatives_composite(
            depth.funding_rate,
            depth.funding_history,
            oi_delta,
        )
        oi_part = ""
        if depth.open_interest is not None:
            oi_part = f"; OI {depth.open_interest:,.0f}"
        return DerivativesResult(
            symbol=normalized,
            funding_rate=depth.funding_rate,
            open_interest=depth.open_interest,
            score=score,
            description=f"{normalized} [{depth.source}]: {desc}{oi_part}",
            source=depth.source,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return derivatives evidence item."""
        del timeframe
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
