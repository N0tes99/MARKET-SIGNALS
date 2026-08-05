"""Alert configuration and test/check endpoints."""

import asyncio

from fastapi import APIRouter, Depends

from app.api.routes.assets import _ASSETS_LIST_CACHE, _load_asset_summaries
from app.core.service_dependencies import (
    get_alert_service,
    get_decision_pipeline,
    get_learning_engine,
)
from app.engines.learning_engine import LearningEngine
from app.schemas.alerts import (
    AlertDispatchSchema,
    AlertEventSchema,
    AlertStatusSchema,
    AlertTestRequest,
)
from app.services.alert_service import AlertService
from app.services.decision_pipeline import DecisionPipelineService

router = APIRouter()


@router.get("/status", response_model=AlertStatusSchema)
async def get_alert_status(
    alerts: AlertService = Depends(get_alert_service),
) -> AlertStatusSchema:
    """Return alert thresholds and which channels are configured."""
    return AlertStatusSchema(**alerts.status())


@router.post("/check", response_model=AlertDispatchSchema)
async def check_alerts(
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
    alerts: AlertService = Depends(get_alert_service),
) -> AlertDispatchSchema:
    """Re-score tracked assets (or use cache) and dispatch threshold alerts."""
    assets = await asyncio.to_thread(
        _ASSETS_LIST_CACHE.get_or_set,
        "dashboard",
        lambda: _load_asset_summaries(pipeline, learning),
    )
    result = await asyncio.to_thread(alerts.dispatch, assets)
    return AlertDispatchSchema(
        enabled=result.enabled,
        evaluated=result.evaluated,
        matched=result.matched,
        sent=result.sent,
        skipped_cooldown=result.skipped_cooldown,
        discord_ok=result.discord_ok,
        email_ok=result.email_ok,
        events=[AlertEventSchema(**event.__dict__) for event in result.events],
    )


@router.post("/test")
async def test_alert(
    body: AlertTestRequest,
    alerts: AlertService = Depends(get_alert_service),
) -> dict:
    """Send a test alert to Discord and/or email."""
    return await asyncio.to_thread(alerts.send_test, body.channel)
