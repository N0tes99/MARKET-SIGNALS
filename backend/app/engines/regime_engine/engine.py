"""Regime Engine — market regime classification."""

from dataclasses import dataclass
from enum import StrEnum

from app.engines.volatility_engine import fetch_vix_level
from app.indicators.atr import calculate_atr
from app.market_data.service import MarketDataService
from app.scoring.weights import ScoringCategory


class MarketRegime(StrEnum):
    """High-level market regime classification."""

    TRENDING = "Trending"
    RANGING = "Ranging"
    VOLATILE = "Volatile"
    QUIET = "Quiet"


@dataclass
class RegimeResult:
    """Market regime classification output."""

    regime: MarketRegime
    confidence: float
    weight_multipliers: dict[ScoringCategory, float]
    description: str


class RegimeEngine:
    """Classifies the current market regime and adjusts scoring weights."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()

    def classify(self, symbol: str, timeframe: str = "1h") -> RegimeResult:
        """Determine the current market regime for an asset."""
        df = self._market_data.safe_get_ohlcv(symbol, timeframe)
        if df is None:
            return RegimeResult(
                regime=MarketRegime.RANGING,
                confidence=0.0,
                weight_multipliers={},
                description=f"{symbol}: Regime unknown — insufficient data",
            )

        atr = calculate_atr(df["high"], df["low"], df["close"])
        atr_pct = (atr / df["close"]).iloc[-20:]
        current_atr_pct = float(atr_pct.iloc[-1])
        avg_atr_pct = float(atr_pct.mean())

        returns = df["close"].pct_change().dropna().tail(20)
        directional_move = abs(float(returns.sum()))

        if current_atr_pct > avg_atr_pct * 1.5:
            regime = MarketRegime.VOLATILE
            multipliers = {
                ScoringCategory.TREND: 0.7,
                ScoringCategory.STRUCTURE: 0.8,
            }
            description = f"{symbol}: Volatile regime — ATR {current_atr_pct:.2%} above average"
        elif current_atr_pct < avg_atr_pct * 0.6:
            regime = MarketRegime.QUIET
            multipliers = {ScoringCategory.MOMENTUM: 0.8}
            description = f"{symbol}: Quiet regime — compressed volatility"
        elif directional_move > 0.03:
            regime = MarketRegime.TRENDING
            multipliers = {}
            description = f"{symbol}: Trending regime — directional move {directional_move:.1%}"
        else:
            regime = MarketRegime.RANGING
            multipliers = {ScoringCategory.TREND: 0.8}
            description = f"{symbol}: Ranging regime — reduced trend weight"

        confidence = min(abs(current_atr_pct - avg_atr_pct) / avg_atr_pct * 100, 100)

        vix = fetch_vix_level(self._market_data)
        if vix is not None and vix >= 25:
            multipliers = {
                **multipliers,
                ScoringCategory.TREND: multipliers.get(ScoringCategory.TREND, 1.0) * 0.85,
                ScoringCategory.STRUCTURE: multipliers.get(ScoringCategory.STRUCTURE, 1.0) * 0.9,
            }
            description = f"{description}; VIX {vix:.1f} suppresses trend/structure weights"

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            weight_multipliers=multipliers,
            description=description,
        )
