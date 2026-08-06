"""Sector / benchmark relative-strength engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.service import MarketDataService
from app.market_data.symbols import AssetClass, get_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score

_LOOKBACK = 20
_MIN_BARS = 12

# Stock → sector / theme ETF already on the watchlist
_SECTOR_ETF: dict[str, str] = {
    "AAPL": "QQQ",
    "MSFT": "QQQ",
    "NVDA": "SMH",
    "GOOGL": "QQQ",
    "META": "QQQ",
    "AMZN": "QQQ",
    "TSLA": "QQQ",
    "AMD": "SMH",
    "NFLX": "QQQ",
    "NOW": "QQQ",
    "CRM": "QQQ",
    "PLTR": "QQQ",
    "COIN": "IBIT",
    "SMCI": "SMH",
    "MSTR": "IBIT",
    "HOOD": "QQQ",
    "RKLB": "QQQ",
    "IONQ": "QQQ",
    "ARM": "SMH",
    "SHOP": "QQQ",
    "SNOW": "QQQ",
    "UBER": "QQQ",
    "RBLX": "QQQ",
}


@dataclass
class SectorRSResult:
    """Relative strength analysis output."""

    score: float
    relative_return_pct: float | None
    benchmark: str | None
    description: str


def benchmarks_for(symbol: str, asset_class: AssetClass) -> tuple[str, ...]:
    """Primary and secondary RS benchmarks for a symbol."""
    if symbol == "BTC":
        return ("SPY",)
    if asset_class == AssetClass.CRYPTO:
        return ("BTC", "SPY")
    if asset_class == AssetClass.STOCK:
        sector = _SECTOR_ETF.get(symbol, "SPY")
        if sector == "SPY":
            return ("SPY",)
        return (sector, "SPY")
    # ETFs: vs SPY (and QQQ for non-broad equity ETFs)
    if symbol in {"SPY", "VOO", "DIA"}:
        return ("QQQ",)
    return ("SPY",)


def period_return(close: pd.Series, lookback: int = _LOOKBACK) -> float | None:
    """Return percentage change over lookback bars."""
    if len(close) < lookback + 1:
        return None
    start = float(close.iloc[-(lookback + 1)])
    end = float(close.iloc[-1])
    if start == 0:
        return None
    return ((end - start) / start) * 100.0


def score_relative_strength(rel_pct: float) -> tuple[float, str]:
    """Map out/under-performance vs benchmark to an evidence score."""
    if rel_pct >= 4.0:
        return clamp_score(68.0), "strong leader"
    if rel_pct >= 1.5:
        return clamp_score(60.0), "leading"
    if rel_pct >= -1.5:
        return clamp_score(52.0), "inline with benchmark"
    if rel_pct >= -4.0:
        return clamp_score(42.0), "lagging"
    return clamp_score(34.0), "hard lagger"


class SectorRSEngine:
    """Scores whether an asset is leading or lagging its benchmarks."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self._market_data = market_data or MarketDataService()

    def analyze(self, symbol: str, timeframe: str = "1h") -> SectorRSResult:
        """Compute relative return vs primary benchmark."""
        normalized = symbol.upper()
        try:
            asset_class = get_asset_class(normalized)
        except ValueError:
            return SectorRSResult(
                score=50.0,
                relative_return_pct=None,
                benchmark=None,
                description="Sector RS: untracked symbol — neutral",
            )

        benches = benchmarks_for(normalized, asset_class)
        # Default limit=200 matches trend/rank_all warm cache key.
        asset_df = self._market_data.safe_get_ohlcv(normalized, timeframe)
        if asset_df is None or len(asset_df) < _MIN_BARS:
            return SectorRSResult(
                score=50.0,
                relative_return_pct=None,
                benchmark=benches[0] if benches else None,
                description="Sector RS: price history unavailable — neutral",
            )

        asset_ret = period_return(asset_df["close"])
        if asset_ret is None:
            return SectorRSResult(
                score=50.0,
                relative_return_pct=None,
                benchmark=benches[0],
                description="Sector RS: insufficient bars — neutral",
            )

        primary = benches[0]
        if primary == normalized:
            primary = benches[1] if len(benches) > 1 else "SPY"

        bench_df = self._market_data.safe_get_ohlcv(primary, timeframe)
        if bench_df is None:
            return SectorRSResult(
                score=50.0,
                relative_return_pct=None,
                benchmark=primary,
                description=f"Sector RS: {primary} history unavailable — neutral",
            )

        bench_ret = period_return(bench_df["close"])
        if bench_ret is None:
            return SectorRSResult(
                score=50.0,
                relative_return_pct=None,
                benchmark=primary,
                description=f"Sector RS: {primary} insufficient bars — neutral",
            )

        rel = asset_ret - bench_ret
        score, tone = score_relative_strength(rel)
        description = (
            f"Sector RS vs {primary}: asset {asset_ret:+.1f}% / "
            f"bench {bench_ret:+.1f}% (α {rel:+.1f}%) — {tone}"
        )
        return SectorRSResult(
            score=score,
            relative_return_pct=rel,
            benchmark=primary,
            description=description,
        )

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return relative-strength evidence."""
        result = self.analyze(symbol, timeframe)
        return [
            EvidenceItem(
                source="sector_rs_engine",
                category=ScoringCategory.SECTOR_RS.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.SECTOR_RS],
                description=result.description,
            )
        ]
