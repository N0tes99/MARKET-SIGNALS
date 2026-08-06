"""Walk-forward weight optimization using historical category scores."""

from dataclasses import dataclass

import pandas as pd

from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_ema
from app.indicators.macd import calculate_macd
from app.indicators.rsi import calculate_rsi
from app.market_data.service import MarketDataService
from app.scoring.calculator import calculate_total_confidence
from app.scoring.presets import WEIGHT_PRESETS
from app.scoring.weight_config import WeightConfig, get_weight_config
from app.scoring.weights import ScoringCategory
from app.utils.scoring_helpers import (
    clamp_score,
    detect_higher_highs_higher_lows,
    score_from_macd_histogram,
    score_from_rsi,
)


@dataclass
class PresetBacktestResult:
    """Backtest outcome for a single weight preset."""

    preset_name: str
    weights: dict[ScoringCategory, float]
    total_signals: int
    win_rate: float
    avg_return_pct: float
    score: float


@dataclass
class WeightTuningResult:
    """Full weight optimization output."""

    symbol: str
    timeframe: str
    active_preset: str
    active_weights: dict[str, float]
    recommended_preset: str
    recommended_weights: dict[str, float]
    results: list[PresetBacktestResult]


def category_scores_at_index(df: pd.DataFrame, idx: int) -> dict[ScoringCategory, float]:
    """Estimate category scores at a historical bar (for replay backtests)."""
    window = df.iloc[: idx + 1]
    close = window["close"]
    if len(close) < 55:
        neutral = 50.0
        return dict.fromkeys(ScoringCategory, neutral)

    price = float(close.iloc[-1])
    ema20 = float(calculate_ema(close, 20).iloc[-1])
    ema50 = float(calculate_ema(close, 50).iloc[-1])
    rsi = float(calculate_rsi(close).iloc[-1])
    _, _, histogram = calculate_macd(close)
    macd_hist = float(histogram.iloc[-1])
    structure = detect_higher_highs_higher_lows(window["high"], window["low"])

    trend = score_from_rsi(rsi)
    momentum = score_from_macd_histogram(macd_hist, price)
    if price < ema20 < ema50 and rsi <= 45:
        trend = clamp_score(100 - trend)
        momentum = clamp_score(100 - momentum)

    vol = window["volume"]
    avg_vol = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())
    vol_ratio = float(vol.iloc[-1]) / avg_vol if avg_vol > 0 else 1.0
    volume = clamp_score(50 + (vol_ratio - 1.0) * 25)

    atr = float(calculate_atr(window["high"], window["low"], close).iloc[-1])
    risk = clamp_score(100 - (atr / price) * 800)

    return {
        ScoringCategory.TREND: trend,
        ScoringCategory.MOMENTUM: momentum,
        ScoringCategory.VOLUME: volume,
        ScoringCategory.STRUCTURE: structure,
        ScoringCategory.RISK: risk,
        ScoringCategory.MACRO: 50.0,
        ScoringCategory.DERIVATIVES: 50.0,
        ScoringCategory.CORRELATION: 50.0,
        ScoringCategory.VOLATILITY: 50.0,
        ScoringCategory.EVENTS: 50.0,
        ScoringCategory.SECTOR_RS: 50.0,
        ScoringCategory.ON_CHAIN: 50.0,
        ScoringCategory.SENTIMENT: 50.0,
    }


def confidence_from_scores(
    scores: dict[ScoringCategory, float],
    weights: dict[ScoringCategory, float],
) -> float:
    """Compute weighted confidence from category scores."""
    from app.engines.evidence_engine.types import EvidenceItem

    items = [
        EvidenceItem("replay", cat.value, scores[cat], weights[cat], "")
        for cat in ScoringCategory
    ]
    return calculate_total_confidence(items, weights=weights)


def _preset_score(win_rate: float, avg_return_pct: float, total_signals: int) -> float:
    """Rank presets: reward return and win rate, penalize too few signals."""
    if total_signals < 3:
        return -999.0
    return (win_rate * 0.4) + (avg_return_pct * 6.0) + (min(total_signals, 20) * 0.5)


class WeightOptimizer:
    """Tests weight presets against walk-forward historical returns."""

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        weight_config: WeightConfig | None = None,
    ) -> None:
        self._market_data = market_data or MarketDataService()
        self._weight_config = weight_config or get_weight_config()

    def optimize(
        self,
        symbol: str,
        timeframe: str = "1h",
        hold_bars: int = 24,
        signal_threshold: float = 55.0,
    ) -> WeightTuningResult:
        """Evaluate all presets; return ranked results and recommendation."""
        df = self._market_data.get_ohlcv(symbol, timeframe, limit=200)
        results: list[PresetBacktestResult] = []

        for preset_name, weights in WEIGHT_PRESETS.items():
            metrics = self._backtest_preset(
                df, weights, hold_bars, signal_threshold
            )
            results.append(
                PresetBacktestResult(
                    preset_name=preset_name,
                    weights=dict(weights),
                    total_signals=metrics["total_signals"],
                    win_rate=metrics["win_rate"],
                    avg_return_pct=metrics["avg_return_pct"],
                    score=metrics["score"],
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        best = results[0]
        active = self._weight_config.get_weights()
        active_preset = self._weight_config.get_preset_name()

        return WeightTuningResult(
            symbol=symbol.upper(),
            timeframe=timeframe,
            active_preset=active_preset,
            active_weights={cat.value: w for cat, w in active.items()},
            recommended_preset=best.preset_name,
            recommended_weights={cat.value: w for cat, w in best.weights.items()},
            results=results,
        )

    def apply_preset(self, preset_name: str) -> dict[ScoringCategory, float]:
        """Apply a named preset as the active runtime weights."""
        if preset_name not in WEIGHT_PRESETS:
            msg = f"Unknown preset '{preset_name}'"
            raise ValueError(msg)
        weights = dict(WEIGHT_PRESETS[preset_name])
        self._weight_config.apply(weights, preset_name=preset_name)
        return weights

    def reset(self) -> None:
        """Restore default weights and re-enable auto-regime."""
        self._weight_config.reset()

    def active_weights(self) -> tuple[str, dict[ScoringCategory, float]]:
        """Return active preset name and weights."""
        return self._weight_config.get_preset_name(), self._weight_config.get_weights()

    def regime_auto(self) -> bool:
        """Whether regime weight-profile swaps are active."""
        return self._weight_config.is_regime_auto()

    def _backtest_preset(
        self,
        df: pd.DataFrame,
        weights: dict[ScoringCategory, float],
        hold_bars: int,
        signal_threshold: float,
    ) -> dict[str, float]:
        """Walk-forward backtest for one weight configuration."""
        returns: list[float] = []
        min_start = 55
        max_idx = len(df) - hold_bars - 1

        if max_idx <= min_start:
            return {
                "total_signals": 0,
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
                "score": -999.0,
            }

        for idx in range(min_start, max_idx):
            scores = category_scores_at_index(df, idx)
            confidence = confidence_from_scores(scores, weights)
            if confidence < signal_threshold:
                continue

            entry = float(df["close"].iloc[idx])
            exit_price = float(df["close"].iloc[idx + hold_bars])
            returns.append(((exit_price - entry) / entry) * 100)

        if not returns:
            return {
                "total_signals": 0,
                "win_rate": 0.0,
                "avg_return_pct": 0.0,
                "score": -999.0,
            }

        wins = sum(1 for r in returns if r > 0)
        win_rate = (wins / len(returns)) * 100
        avg_return = sum(returns) / len(returns)

        return {
            "total_signals": len(returns),
            "win_rate": round(win_rate, 1),
            "avg_return_pct": round(avg_return, 2),
            "score": round(_preset_score(win_rate, avg_return, len(returns)), 2),
        }
