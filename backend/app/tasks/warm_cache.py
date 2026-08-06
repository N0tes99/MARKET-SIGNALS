"""Celery tasks for market-data and decision warm-cache."""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.warm_cache.warm_market_and_decisions")
def warm_market_and_decisions(timeframe: str = "1h") -> dict[str, int | str]:
    """Prefetch OHLCV for tracked symbols and warm the decision evaluate cache."""
    from app.api.tracked import TRACKED_SYMBOLS
    from app.core.service_dependencies import get_decision_pipeline, get_market_data_service

    market_data = get_market_data_service()
    pipeline = get_decision_pipeline()
    symbols = list(TRACKED_SYMBOLS)

    market_data.warm(symbols, timeframe=timeframe, limit=200)
    decisions = pipeline.rank_all(symbols, timeframe=timeframe)

    logger.info(
        "Warm cache complete: %s symbols prefetched, %s decisions ranked",
        len(symbols),
        len(decisions),
    )
    return {
        "status": "ok",
        "symbols": len(symbols),
        "decisions": len(decisions),
        "timeframe": timeframe,
    }
