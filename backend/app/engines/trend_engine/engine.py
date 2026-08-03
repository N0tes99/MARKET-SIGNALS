"""Trend Engine — determines market direction."""

from dataclasses import dataclass
from enum import StrEnum

from app.engines.evidence_engine.types import EvidenceItem
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.market_data.service import MarketDataService
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import (
    clamp_score,
    detect_higher_highs_higher_lows,
    score_from_macd_histogram,
    score_from_rsi,
)


class TrendDirection(StrEnum):
    """Market trend direction classification."""

    BULLISH = "Bullish"
    NEUTRAL = "Neutral"
    BEARISH = "Bearish"


@dataclass
class TrendResult:
    """Trend analysis output for a single asset."""

    symbol: str
    direction: TrendDirection
    confidence: float
    structure_score: float
    rsi: float
    description: str


class TrendEngine:
    """Analyzes price structure to determine market direction."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        """Initialize with optional market data service."""
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str, timeframe: str = "1h") -> TrendResult | None:
        """Determine trend direction and confidence for an asset."""
        df = self._market_data.safe_get_ohlcv(symbol, timeframe)
        if df is None:
            return None

        close = df["close"]
        price = float(close.iloc[-1])
        ema20 = float(calculate_ema(close, 20).iloc[-1])
        ema50 = float(calculate_ema(close, 50).iloc[-1])
        rsi = float(calculate_rsi(close).iloc[-1])
        _, _, histogram = calculate_macd(close)
        macd_hist = float(histogram.iloc[-1])
        structure_score = detect_higher_highs_higher_lows(df["high"], df["low"])

        if price > ema20 > ema50 and rsi >= 55:
            direction = TrendDirection.BULLISH
        elif price < ema20 < ema50 and rsi <= 45:
            direction = TrendDirection.BEARISH
        else:
            direction = TrendDirection.NEUTRAL

        trend_score = score_from_rsi(rsi)
        macd_score = score_from_macd_histogram(macd_hist, price)
        confidence = clamp_score((trend_score * 0.5) + (macd_score * 0.3) + (structure_score * 0.2))

        if direction == TrendDirection.BEARISH:
            confidence = clamp_score(100 - confidence)

        description = (
            f"{symbol}: {direction} — price {price:.2f}, EMA20 {ema20:.2f}, "
            f"EMA50 {ema50:.2f}, RSI {rsi:.1f}"
        )

        return TrendResult(
            symbol=symbol.upper(),
            direction=direction,
            confidence=confidence,
            structure_score=structure_score,
            rsi=rsi,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return trend and structure evidence items."""
        result = self.analyze(symbol, timeframe)
        if result is None:
            return [
                EvidenceItem(
                    source="trend_engine",
                    category=ScoringCategory.TREND.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.TREND],
                    description=f"{symbol}: Trend data unavailable",
                ),
                EvidenceItem(
                    source="trend_engine",
                    category=ScoringCategory.STRUCTURE.value,
                    score=0.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.STRUCTURE],
                    description=f"{symbol}: Structure data unavailable",
                ),
            ]

        return [
            EvidenceItem(
                source="trend_engine",
                category=ScoringCategory.TREND.value,
                score=result.confidence,
                weight=DEFAULT_WEIGHTS[ScoringCategory.TREND],
                description=result.description,
            ),
            EvidenceItem(
                source="trend_engine",
                category=ScoringCategory.STRUCTURE.value,
                score=result.structure_score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.STRUCTURE],
                description=(
                    f"{symbol}: Market structure score {result.structure_score:.0f} "
                    f"from recent swing highs/lows"
                ),
            ),
        ]
