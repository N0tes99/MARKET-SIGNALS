"""Buyer/Seller Engine — order flow analysis."""

from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.indicators.volume import calculate_buying_pressure, calculate_volume_ratio
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score


@dataclass
class OrderFlowResult:
    """Order flow analysis output."""

    symbol: str
    buyer_strength: float
    seller_strength: float
    absorption: float
    momentum: float
    volume_ratio: float
    description: str


class BuyerSellerEngine:
    """Measures buyer/seller dynamics from price and volume."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str, timeframe: str = "1h") -> OrderFlowResult | None:
        """Analyze order flow proxies for an asset."""
        df = self._market_data.safe_get_ohlcv(symbol, timeframe)
        if df is None:
            return None

        close = df["close"]
        volume = df["volume"]
        volume_ratio = float(calculate_volume_ratio(volume).iloc[-1])
        buying_pressure = float(
            calculate_buying_pressure(df["open"], close, volume).iloc[-1]
        )
        seller_strength = clamp_score(100 - buying_pressure)

        returns = close.pct_change().dropna()
        momentum = clamp_score(50 + float(returns.tail(10).mean()) * 5000)

        # Absorption: high volume with small price change suggests absorption
        recent_range = (df["high"].iloc[-1] - df["low"].iloc[-1]) / close.iloc[-1]
        absorption = clamp_score(min(volume_ratio * 30, 100) if recent_range < 0.005 else 40)

        description = (
            f"{symbol}: Buying pressure {buying_pressure:.0f}%, "
            f"volume {volume_ratio:.2f}x average, momentum {momentum:.0f}"
        )

        return OrderFlowResult(
            symbol=symbol.upper(),
            buyer_strength=buying_pressure,
            seller_strength=seller_strength,
            absorption=absorption,
            momentum=momentum,
            volume_ratio=volume_ratio,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return momentum and volume evidence items."""
        result = self.analyze(symbol, timeframe)
        if result is None:
            return [
                EvidenceItem(
                    source="buyer_seller_engine",
                    category=ScoringCategory.MOMENTUM.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM],
                    description=f"{symbol}: Momentum data unavailable",
                ),
                EvidenceItem(
                    source="buyer_seller_engine",
                    category=ScoringCategory.VOLUME.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.VOLUME],
                    description=f"{symbol}: Volume data unavailable",
                ),
            ]

        volume_score = clamp_score(min(result.volume_ratio * 50, 100))

        return [
            EvidenceItem(
                source="buyer_seller_engine",
                category=ScoringCategory.MOMENTUM.value,
                score=result.momentum,
                weight=DEFAULT_WEIGHTS[ScoringCategory.MOMENTUM],
                description=result.description,
            ),
            EvidenceItem(
                source="buyer_seller_engine",
                category=ScoringCategory.VOLUME.value,
                score=volume_score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.VOLUME],
                description=(
                    f"{symbol}: Volume at {result.volume_ratio:.2f}x 20-period average, "
                    f"absorption score {result.absorption:.0f}"
                ),
            ),
        ]
