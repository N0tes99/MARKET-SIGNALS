"""Background Celery tasks package."""

from app.tasks import warm_cache as warm_cache

__all__ = ["warm_cache"]
