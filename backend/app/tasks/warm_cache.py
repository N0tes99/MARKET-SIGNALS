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


@celery_app.task(name="app.tasks.warm_cache.tick_paper_agent")
def tick_paper_agent() -> dict[str, int | str | list[str]]:
    """Advance paper bot discovery/management without requiring a dashboard visit."""
    from app.core.service_dependencies import get_paper_agent

    agent = get_paper_agent()
    notes = agent.tick()
    opens = sum(1 for n in notes if n.startswith("open:"))
    logger.info("Paper agent scheduled tick opens=%d notes=%s", opens, notes[:12])
    return {
        "status": "ok",
        "opens": opens,
        "notes": notes[:20],
    }
