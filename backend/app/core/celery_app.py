"""Celery application instance for background task processing."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "signal_engine",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.warm_cache"],
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
            "schedule": 300.0,
        },
    },
)
