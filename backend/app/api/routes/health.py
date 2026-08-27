"""Health check endpoints."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from app.config import settings
from app.schemas.health import AlembicHealth, HealthResponse, StoreBackends, WarehouseHealth

logger = logging.getLogger(__name__)

router = APIRouter()

# Keep-warm and the Chart page poll /health with a ~3s client timeout.
# Constructing PaperAgent (scanners + pipeline + cortex) on this path made
# production health take ~5s after a Render sleep and starved cron-tick.
_BACKENDS_TTL_SECONDS = 30.0
_LAKE_TTL_SECONDS = 15.0
_backends_cache: tuple[float, StoreBackends] | None = None
_lake_cache: tuple[float, WarehouseHealth | None, AlembicHealth | None] | None = None


def _probe_store_backends() -> StoreBackends:
    """Report durable backends without constructing PaperAgent / AlertService."""
    global _backends_cache
    now = time.monotonic()
    cached = _backends_cache
    if cached is not None and now - cached[0] < _BACKENDS_TTL_SECONDS:
        return cached[1]

    mode = settings.signal_store.lower().strip()
    if mode == "memory":
        backends = StoreBackends(learning="memory", paper="memory", alerts="memory")
        _backends_cache = (now, backends)
        return backends

    reachable = False
    try:
        from sqlalchemy import create_engine, text

        from app.engines.learning_engine.postgres_store import to_sync_database_url

        engine = create_engine(
            to_sync_database_url(settings.database_url),
            pool_pre_ping=True,
            pool_timeout=2,
            connect_args={"connect_timeout": 2},
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            reachable = True
        finally:
            engine.dispose()
    except Exception:
        logger.debug("Health store probe skipped", exc_info=True)

    name = "postgres" if reachable else "memory"
    backends = StoreBackends(learning=name, paper=name, alerts=name)
    _backends_cache = (now, backends)
    return backends


def _lake_ops() -> tuple[WarehouseHealth | None, AlembicHealth | None]:
    """Warehouse + alembic snapshot, cached so health stays a cheap ping."""
    global _lake_cache
    now = time.monotonic()
    cached = _lake_cache
    if cached is not None and now - cached[0] < _LAKE_TTL_SECONDS:
        return cached[1], cached[2]

    warehouse: WarehouseHealth | None = None
    alembic: AlembicHealth | None = None
    try:
        from app.data_lake.ops import lake_ops_snapshot

        snap = lake_ops_snapshot()
        warehouse = WarehouseHealth(**snap["warehouse"])  # type: ignore[arg-type]
        alembic = AlembicHealth(**snap["alembic"])  # type: ignore[arg-type]
    except Exception:
        warehouse = None
        alembic = None
    _lake_cache = (now, warehouse, alembic)
    return warehouse, alembic


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Cheap liveness for load balancers, keep-warm, and the Chart page."""
    warehouse, alembic = _lake_ops()
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version="0.1.0",
        environment=settings.app_env,
        stores=_probe_store_backends(),
        warehouse=warehouse,
        alembic=alembic,
    )
