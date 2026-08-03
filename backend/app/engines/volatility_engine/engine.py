"""Volatility regime engine — VIX and market fear gauge analysis."""

import logging
from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_VIX_SYMBOL = "^VIX"
_VIX_CACHE: TTLCache[float | None] = TTLCache(ttl_seconds=300.0)


@dataclass
class VolatilityResult:
    """Volatility regime analysis output."""

    vix: float | None
    score: float
    description: str


def score_from_vix(vix: float) -> tuple[float, str]:
    """Map VIX level to a risk-appetite score (lower VIX = more supportive)."""
    if vix < 15:
        return clamp_score(62.0), f"VIX {vix:.1f} — low fear, supportive risk appetite"
    if vix < 20:
        return clamp_score(56.0), f"VIX {vix:.1f} — normal volatility regime"
    if vix < 25:
        return clamp_score(48.0), f"VIX {vix:.1f} — elevated uncertainty"
    if vix < 30:
        return clamp_score(40.0), f"VIX {vix:.1f} — high fear, reduce conviction"
    return clamp_score(32.0), f"VIX {vix:.1f} — extreme fear, capital protection mode"


def fetch_vix_level(market_data: MarketDataService) -> float | None:
    """Fetch the latest VIX level via Yahoo Finance (cached ~5 min)."""

    def _load() -> float | None:
        try:
            snapshot = market_data.get_ticker(_VIX_SYMBOL)
            return float(snapshot.price)
        except Exception:
            logger.exception("Failed to fetch VIX")
            return None

    return _VIX_CACHE.get_or_set("vix_level", _load)


class VolatilityEngine:
    """Analyzes market-wide volatility regime using VIX."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self._market_data = market_data or MarketDataService()

    def analyze(self) -> VolatilityResult:
        """Return current VIX-based volatility assessment."""
        vix = fetch_vix_level(self._market_data)
        if vix is None:
            return VolatilityResult(
                vix=None,
                score=50.0,
                description="Volatility: VIX unavailable — neutral score",
            )

        score, description = score_from_vix(vix)
        return VolatilityResult(vix=vix, score=score, description=description)

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return volatility regime evidence (global, not per-symbol)."""
        del symbol, timeframe
        result = self.analyze()
        return [
            EvidenceItem(
                source="volatility_engine",
                category=ScoringCategory.VOLATILITY.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.VOLATILITY],
                description=result.description,
            )
        ]
