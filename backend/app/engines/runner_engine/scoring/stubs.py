"""Score all Radar dimensions: live tape + Yahoo snapshot."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.engines.runner_engine.config import RunnerConfig, default_runner_config
from app.engines.runner_engine.scoring.asymmetry import score_asymmetry
from app.engines.runner_engine.scoring.edgar import fetch_edgar_snapshot
from app.engines.runner_engine.scoring.structure import score_structure
from app.engines.runner_engine.scoring.yahoo_dims import (
    score_catalyst,
    score_discovery_gap,
    score_fundamental,
    score_institutional,
    score_short_squeeze,
    score_theme_bottleneck,
)
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    YahooRunnerSnapshot,
    fetch_yahoo_runner_snapshot,
)
from app.engines.runner_engine.types import DimensionScore, RunnerTapeSnapshot
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)

SnapshotFetcher = Callable[[str], YahooRunnerSnapshot]


def score_all_dimensions(
    symbol: str,
    *,
    market_data: MarketDataService | None = None,
    config: RunnerConfig | None = None,
    snapshot: YahooRunnerSnapshot | None = None,
    snapshot_fetcher: SnapshotFetcher | None = None,
) -> tuple[dict[str, DimensionScore], RunnerTapeSnapshot]:
    """Structure/asymmetry from tape; remaining dims from one Yahoo snapshot."""
    normalized = symbol.upper().strip()
    md = market_data or MarketDataService()
    cfg = config or default_runner_config()
    structure, tape = score_structure(normalized, market_data=md)
    snap = snapshot or (snapshot_fetcher or fetch_yahoo_runner_snapshot)(normalized)
    edgar = fetch_edgar_snapshot(normalized)

    dimensions = {
        "fundamental": score_fundamental(snap),
        "catalyst": score_catalyst(snap, edgar=edgar),
        "structure": structure,
        "asymmetry": score_asymmetry(normalized, market_data=md, config=cfg),
        "discovery_gap": score_discovery_gap(snap),
        "theme_bottleneck": score_theme_bottleneck(snap),
        "institutional_accum": score_institutional(snap),
        "short_squeeze_potential": score_short_squeeze(snap),
    }
    for name, dim in dimensions.items():
        logger.info(
            "runner_dimension name=%s score=%.1f quality=%s",
            name,
            dim.score,
            dim.data_quality,
        )
    return dimensions, tape
