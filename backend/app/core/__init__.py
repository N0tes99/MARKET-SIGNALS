"""Core application utilities and shared infrastructure."""

from app.core.celery_app import celery_app

__all__ = ["celery_app"]
