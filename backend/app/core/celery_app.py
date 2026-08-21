"""Celery application instance for background task processing."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "signal_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.warm_cache", "app.tasks.cortex_tick", "app.tasks.memory_consolidation"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "warm-market-and-decisions": {
            "task": "app.tasks.warm_cache.warm_market_and_decisions",
            "schedule": 300.0,
            "args": ("1h",),
        },
        "tick-paper-agent": {
            "task": "app.tasks.warm_cache.tick_paper_agent",
            "schedule": 90.0,
        },
        "warm-reddit-social": {
            "task": "app.tasks.warm_cache.warm_reddit_social",
            "schedule": 900.0,
        },
        "cortex-expansion-tick": {
            "task": "app.tasks.cortex_tick.run_cortex_tick",
            "schedule": 120.0,
        },
        "cortex-semantic-consolidate": {
            "task": "app.tasks.memory_consolidation.consolidate",
            "schedule": 21600.0,
        },
    },
)
