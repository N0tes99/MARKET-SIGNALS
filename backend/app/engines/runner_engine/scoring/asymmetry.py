"""Asymmetry dimension — market-cap buckets from Yahoo fast_info."""

from __future__ import annotations

import logging

from app.engines.runner_engine.config import MarketCapBucket, RunnerConfig
from app.engines.runner_engine.types import DimensionScore
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)


def score_asymmetry(
    symbol: str,
    *,
    market_data: MarketDataService,
    config: RunnerConfig,
) -> DimensionScore:
    """Map market cap to an asymmetry hint. Missing when cap is unknown."""
    normalized = symbol.upper().strip()
    try:
        ticker = market_data.get_ticker(normalized)
        cap = ticker.market_cap
    except Exception:
        logger.info("runner_asymmetry ticker failed for %s", normalized)
        cap = None

    if cap is None or cap <= 0:
        return DimensionScore(
            name="asymmetry",
            score=50.0,
            confidence=0.35,
            factors=[f"{normalized}: market-cap unavailable"],
            conflicts=["Insufficient data for high-conviction runner ranking"],
            data_quality="missing",
        )

    bucket = _bucket_for(cap, config.market_cap_buckets)
    billions = cap / 1_000_000_000.0
    logger.info(
        "runner_dimension name=asymmetry score=%.1f quality=good cap=%.2fB bucket=%s",
        bucket.asymmetry_hint,
        billions,
        bucket.label,
    )
    return DimensionScore(
        name="asymmetry",
        score=bucket.asymmetry_hint,
        confidence=0.7,
        factors=[
            f"Market cap ${billions:.2f}B — {bucket.label} asymmetry band",
        ],
        conflicts=[],
        data_quality="good",
    )


def _bucket_for(
    market_cap_usd: float,
    buckets: tuple[MarketCapBucket, ...],
) -> MarketCapBucket:
    for bucket in buckets:
        if bucket.max_mcap_usd is None or market_cap_usd < bucket.max_mcap_usd:
            return bucket
    return buckets[-1]
