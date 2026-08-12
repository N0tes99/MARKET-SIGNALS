"""Structure dimension — Layer 3 momentum + Sector RS on daily bars."""

from __future__ import annotations

import logging

from app.engines.opportunity_engine.equity_options.momentum import compute_momentum
from app.engines.runner_engine.types import DimensionScore, RunnerTapeSnapshot
from app.engines.sector_rs_engine.engine import (
    benchmarks_for_equity,
    period_return,
    score_relative_strength,
)
from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)


def score_structure(
    symbol: str,
    *,
    market_data: MarketDataService,
) -> tuple[DimensionScore, RunnerTapeSnapshot]:
    """Score market structure from daily OHLCV. Missing if bars are thin."""
    normalized = symbol.upper().strip()
    tape = RunnerTapeSnapshot()
    try:
        ohlcv = market_data.get_ohlcv(normalized, "1d", limit=80, min_rows=55)
    except Exception:
        logger.info("runner_structure no daily bars for %s", normalized)
        return (
            DimensionScore(
                name="structure",
                score=50.0,
                confidence=0.35,
                factors=["No daily OHLCV for structure score"],
                conflicts=["Insufficient data for high-conviction runner ranking"],
                data_quality="missing",
            ),
            tape,
        )

    snap = compute_momentum(ohlcv)
    if snap is None:
        return (
            DimensionScore(
                name="structure",
                score=50.0,
                confidence=0.35,
                factors=["Momentum snapshot unavailable (<55 daily bars)"],
                conflicts=["Insufficient data for high-conviction runner ranking"],
                data_quality="missing",
            ),
            tape,
        )

    tape.ret_20d_pct = snap.ret_20d_pct
    tape.relative_volume = snap.relative_volume
    tape.structure_score = snap.momentum_score

    rs_score, rs_bench, rs_pct, rs_line = _daily_rs(normalized, market_data)
    tape.rs_benchmark = rs_bench
    tape.rs_pct = rs_pct

    blended = clamp_score(0.70 * snap.momentum_score + 0.30 * rs_score)
    tape.structure_score = blended

    factors = [f"Momentum {snap.momentum_score:.0f}"]
    factors.extend(snap.factors[:4])
    if rs_line:
        factors.append(rs_line)
    conflicts = list(snap.conflicts[:4])

    logger.info(
        "runner_dimension name=structure score=%.1f quality=good symbol=%s",
        blended,
        normalized,
    )
    return (
        DimensionScore(
            name="structure",
            score=blended,
            confidence=0.85,
            factors=factors,
            conflicts=conflicts,
            data_quality="good",
        ),
        tape,
    )


def _daily_rs(
    symbol: str,
    market_data: MarketDataService,
) -> tuple[float, str | None, float | None, str | None]:
    benches = benchmarks_for_equity(symbol)
    primary = benches[0]
    if primary == symbol and len(benches) > 1:
        primary = benches[1]
    asset_df = market_data.safe_get_ohlcv(symbol, "1d", limit=80)
    bench_df = market_data.safe_get_ohlcv(primary, "1d", limit=80)
    if asset_df is None or bench_df is None:
        return 50.0, primary, None, None
    asset_ret = period_return(asset_df["close"])
    bench_ret = period_return(bench_df["close"])
    if asset_ret is None or bench_ret is None:
        return 50.0, primary, None, None
    rel = asset_ret - bench_ret
    score, tone = score_relative_strength(rel)
    line = f"RS vs {primary}: α {rel:+.1f}% — {tone}"
    return score, primary, rel, line
