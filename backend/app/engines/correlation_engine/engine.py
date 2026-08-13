"""Cross-asset correlation engine — benchmark coupling analysis."""

from dataclasses import dataclass

import pandas as pd

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.service import MarketDataService
from app.market_data.symbols import AssetClass, resolve_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score

_CORRELATION_WINDOW = 20
_MIN_BARS = 10


@dataclass
class CorrelationResult:
    """Cross-asset correlation analysis output."""

    score: float
    correlations: dict[str, float]
    description: str


def _benchmarks_for(symbol: str, asset_class: AssetClass) -> tuple[str, ...]:
    """Return reference symbols for correlation analysis."""
    if symbol == "BTC":
        return ("SPY", "QQQ")
    if asset_class == AssetClass.CRYPTO:
        return ("BTC", "SPY")
    if asset_class == AssetClass.STOCK:
        return ("SPY", "QQQ")
    return ("SPY",)


def _returns(series: pd.Series) -> pd.Series:
    return series.pct_change().dropna()


def _rolling_correlation(left: pd.Series, right: pd.Series) -> float | None:
    """Compute Pearson correlation on aligned return series."""
    aligned = pd.concat([left, right], axis=1, join="inner").dropna().tail(_CORRELATION_WINDOW)
    if len(aligned) < _MIN_BARS:
        return None
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))


def _score_from_correlations(correlations: dict[str, float]) -> tuple[float, str]:
    """Map benchmark correlations to an evidence score."""
    if not correlations:
        return 50.0, "Correlation data unavailable"

    avg_abs = sum(abs(value) for value in correlations.values()) / len(correlations)
    strongest = max(correlations.items(), key=lambda item: abs(item[1]))
    bench, value = strongest

    if avg_abs >= 0.75:
        score = clamp_score(42.0)
        tone = "high beta coupling"
    elif avg_abs >= 0.45:
        score = clamp_score(52.0)
        tone = "moderate benchmark coupling"
    elif value < 0:
        score = clamp_score(58.0)
        tone = "negative coupling (diversifier)"
    else:
        score = clamp_score(62.0)
        tone = "decoupled / independent move"

    parts = ", ".join(f"{name} {corr:+.2f}" for name, corr in correlations.items())
    description = f"Correlation vs {parts} — {tone}"
    return score, description


class CorrelationEngine:
    """Measures how tightly an asset tracks key benchmarks."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str, timeframe: str = "1h") -> CorrelationResult | None:
        """Compute rolling correlations against benchmark symbols."""
        normalized = symbol.upper()
        asset_class = resolve_asset_class(normalized)
        if asset_class is None:
            return None
        benchmarks = _benchmarks_for(normalized, asset_class)

        # Default limit=200 matches trend/rank_all warm cache key.
        asset_df = self._market_data.safe_get_ohlcv(normalized, timeframe)
        if asset_df is None:
            return None

        asset_returns = _returns(asset_df["close"])
        correlations: dict[str, float] = {}

        for benchmark in benchmarks:
            if benchmark == normalized:
                continue
            bench_df = self._market_data.safe_get_ohlcv(benchmark, timeframe)
            if bench_df is None:
                continue
            corr = _rolling_correlation(asset_returns, _returns(bench_df["close"]))
            if corr is not None:
                correlations[benchmark] = round(corr, 3)

        score, description = _score_from_correlations(correlations)
        return CorrelationResult(score=score, correlations=correlations, description=description)

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return cross-asset correlation evidence."""
        result = self.analyze(symbol, timeframe)
        if result is None:
            return [
                EvidenceItem(
                    source="correlation_engine",
                    category=ScoringCategory.CORRELATION.value,
                    score=50.0,
                    weight=DEFAULT_WEIGHTS[ScoringCategory.CORRELATION],
                    description=f"{symbol.upper()}: Correlation data unavailable",
                )
            ]

        return [
            EvidenceItem(
                source="correlation_engine",
                category=ScoringCategory.CORRELATION.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.CORRELATION],
                description=result.description,
            )
        ]
