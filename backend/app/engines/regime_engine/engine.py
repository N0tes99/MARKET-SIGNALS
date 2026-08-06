"""Regime Engine — market regime classification."""

from dataclasses import dataclass
from enum import StrEnum

from app.engines.volatility_engine import fetch_vix_level
from app.indicators.atr import calculate_atr
from app.market_data.service import MarketDataService
from app.scoring.weights import WeightProfile, resolve_weight_profile


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
    weight_profile: WeightProfile
    description: str
    vix: float | None = None


class RegimeEngine:
    """Classifies the current market regime for scoring weight profile selection."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()

    def classify(self, symbol: str, timeframe: str = "1h") -> RegimeResult:
        """Determine the current market regime for an asset."""
        df = self._market_data.safe_get_ohlcv(symbol, timeframe)
        vix = fetch_vix_level(self._market_data)

        if df is None:
            profile = resolve_weight_profile(MarketRegime.RANGING.value, vix=vix)
            return RegimeResult(
                regime=MarketRegime.RANGING,
                confidence=0.0,
                weight_profile=profile,
                description=f"{symbol}: Regime unknown — insufficient data",
                vix=vix,
            )

        atr = calculate_atr(df["high"], df["low"], df["close"])
        atr_pct = (atr / df["close"]).iloc[-20:]
        current_atr_pct = float(atr_pct.iloc[-1])
        avg_atr_pct = float(atr_pct.mean())

        returns = df["close"].pct_change().dropna().tail(20)
        directional_move = abs(float(returns.sum()))

        if current_atr_pct > avg_atr_pct * 1.5:
            regime = MarketRegime.VOLATILE
            description = f"{symbol}: Volatile regime — ATR {current_atr_pct:.2%} above average"
        elif current_atr_pct < avg_atr_pct * 0.6:
            regime = MarketRegime.QUIET
            description = f"{symbol}: Quiet regime — compressed volatility"
        elif directional_move > 0.03:
            regime = MarketRegime.TRENDING
            description = f"{symbol}: Trending regime — directional move {directional_move:.1%}"
        else:
            regime = MarketRegime.RANGING
            description = f"{symbol}: Ranging regime — choppy weight profile"

        confidence = min(abs(current_atr_pct - avg_atr_pct) / avg_atr_pct * 100, 100)
        weight_profile = resolve_weight_profile(regime.value, vix=vix)

        if vix is not None and vix >= 25:
            description = f"{description}; VIX {vix:.1f} → High-vol weight profile"

        return RegimeResult(
            regime=regime,
            confidence=round(confidence, 2),
            weight_profile=weight_profile,
            description=description,
            vix=vix,
        )
