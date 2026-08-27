"""Health check endpoints."""

from fastapi import APIRouter

from app.config import settings
from app.core.service_dependencies import (
    get_alert_service,
    get_learning_engine,
    get_paper_agent,
)
from app.schemas.health import AlembicHealth, HealthResponse, StoreBackends, WarehouseHealth

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status for load balancers and monitoring."""
    learning = get_learning_engine()
    paper = get_paper_agent()
    alerts = get_alert_service()
    learning_backend = getattr(getattr(learning, "_store", None), "backend", "unknown")
    paper_backend = getattr(getattr(paper, "_store", None), "backend", "unknown")
    alert_backend = getattr(alerts, "_backend", "unknown")
    warehouse = None
    alembic = None
    try:
        from app.data_lake.ops import lake_ops_snapshot

        snap = lake_ops_snapshot()
        warehouse = WarehouseHealth(**snap["warehouse"])  # type: ignore[arg-type]
        alembic = AlembicHealth(**snap["alembic"])  # type: ignore[arg-type]
    except Exception:
        warehouse = None
        alembic = None
    return HealthResponse(
        status="healthy",
        app_name=settings.app_name,
        version="0.1.0",
        environment=settings.app_env,
        stores=StoreBackends(
            learning=learning_backend,
            paper=paper_backend,
            alerts=alert_backend,
        ),
        warehouse=warehouse,
        alembic=alembic,
    )
