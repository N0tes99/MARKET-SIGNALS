"""Evidence Engine — central evidence accumulation system."""

from app.engines.evidence_engine.collectors import build_collectors
from app.engines.evidence_engine.protocol import EvidenceContributor
from app.engines.evidence_engine.types import EvidenceBundle, EvidenceItem
from app.engines.regime_engine import RegimeEngine
from app.market_data.service import MarketDataService
from app.scoring.calculator import calculate_total_confidence
from app.scoring.weight_config import get_weight_config
from app.scoring.weights import REGIME_WEIGHT_PROFILES


class EvidenceEngine:
    """Collects and aggregates evidence from all analysis engines.

    The Evidence Engine NEVER predicts. It accumulates weighted evidence
    from specialized engines and produces an ``EvidenceBundle``.
    """

    def __init__(
        self,
        collectors: list[EvidenceContributor] | None = None,
        regime_engine: RegimeEngine | None = None,
        market_data: MarketDataService | None = None,
    ) -> None:
        """Initialize with optional custom collectors and regime engine."""
        self._market_data = market_data or MarketDataService()
        self._collectors = collectors or build_collectors(self._market_data)
        self._regime_engine = regime_engine or RegimeEngine(self._market_data)

    def accumulate(self, symbol: str, timeframe: str = "1h") -> EvidenceBundle:
        """Gather evidence from all engines for the given asset.

        Args:
            symbol: Asset ticker symbol (e.g. ``BTC``).
            timeframe: Candle timeframe used for analysis.

        Returns:
            Aggregated evidence bundle with weighted confidence score.
        """
        normalized_symbol = symbol.upper()
        items: list[EvidenceItem] = []

        for collector in self._collectors:
            items.extend(collector.contribute_evidence(normalized_symbol, timeframe))

        regime = self._regime_engine.classify(normalized_symbol, timeframe)
        weight_config = get_weight_config()
        if weight_config.is_regime_auto():
            active_weights = REGIME_WEIGHT_PROFILES[regime.weight_profile]
        else:
            active_weights = weight_config.get_weights()

        total_confidence = calculate_total_confidence(items, weights=active_weights)

        return EvidenceBundle(
            symbol=normalized_symbol,
            timeframe=timeframe,
            items=items,
            total_confidence=total_confidence,
            regime=regime.regime.value,
            regime_confidence=regime.confidence,
        )
