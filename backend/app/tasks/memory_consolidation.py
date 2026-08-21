"""Episodic → semantic consolidation (Celery)."""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.memory_consolidation.consolidate")
def consolidate_memory() -> dict:
    """Rebuild lead-time / calibration stats from stored cortex ticks."""
    from app.core.service_dependencies import get_cortex_orchestrator
    from app.memory.semantic.consolidator import consolidate_from_episodic

    try:
        orch = get_cortex_orchestrator()
        stats = consolidate_from_episodic(orch.episodic, orch.semantic)
    except Exception:
        logger.warning("memory_consolidation failed", exc_info=True)
        return {"status": "error", "stats": 0}

    logger.info("memory_consolidation wrote %s stats", len(stats))
    return {
        "status": "ok",
        "stats": len(stats),
        "metrics": [f"{s.metric}:{s.signal}:{s.score_bucket}" for s in stats],
    }
