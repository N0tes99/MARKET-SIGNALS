"""Celery tasks for cortex brain heartbeat."""

from __future__ import annotations

import logging

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.cortex_tick.run_cortex_tick")
def run_cortex_tick() -> dict[str, str | int | list[str]]:
    """Advance cortex working memory — specialist collaboration tick."""
    from app.core.service_dependencies import get_cortex_orchestrator

    try:
        orchestrator = get_cortex_orchestrator()
        memory = orchestrator.tick(persist=True)
    except Exception:
        logger.warning("run_cortex_tick failed", exc_info=True)
        return {"status": "error", "tick_id": "", "notes": []}

    alert_notes: list[str] = []
    try:
        from app.core.service_dependencies import get_alert_service
        from app.services.expansion_alert_service import get_expansion_alert_service

        alert_notes = get_expansion_alert_service().notify_memory(
            memory, get_alert_service()
        )
    except Exception:
        logger.warning("expansion alerts failed", exc_info=True)

    logger.info("Cortex tick complete: %s", orchestrator.digest())
    return {
        "status": "ok",
        "tick_id": memory.tick_id,
        "notes": memory.notes[:10] + alert_notes[:5],
        "primed": memory.primed_symbols(),
        "triggering": memory.triggering_symbols(),
        "alerts_sent": len(alert_notes),
    }
