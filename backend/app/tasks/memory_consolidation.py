"""Weekly episodic → semantic consolidation (Phase B Celery task)."""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.memory_consolidation.consolidate")
def consolidate_memory() -> dict:
    """Stub: aggregate episodic ticks into semantic lead-time stats."""
    logger.info("memory_consolidation stub — Phase B")
    return {"status": "stub", "message": "Enable after semantic memory persistence"}
