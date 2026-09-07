"""Core application utilities and shared infrastructure."""

# Do not import celery_app here — constructing Celery on `import app.core`
# delays uvicorn bind on the free Render web dyno (no worker anyway).
# Tasks import `app.core.celery_app` directly.

__all__: list[str] = []
