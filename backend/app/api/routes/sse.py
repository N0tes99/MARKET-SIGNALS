"""Server-sent dashboard updates (works through the Next.js HTTP proxy)."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, Request
from starlette.responses import StreamingResponse

from app.api.routes.assets import _get_dashboard
from app.core.service_dependencies import get_decision_pipeline, get_learning_engine
from app.engines.learning_engine import LearningEngine
from app.services.decision_pipeline import DecisionPipelineService

logger = logging.getLogger(__name__)

router = APIRouter()
_BROADCAST_INTERVAL_SECONDS = 30


def _dashboard_event(
    pipeline: DecisionPipelineService,
    learning: LearningEngine,
) -> dict:
    dashboard = _get_dashboard(pipeline, learning, sync=False)
    return dashboard.model_dump(mode="json")


@router.get("/dashboard")
async def dashboard_sse(
    request: Request,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
    once: bool = Query(False, description="Send one event and close (tests/health)"),
) -> StreamingResponse:
    """Push the same payload as GET /assets, every 30s, over SSE."""

    async def events():
        try:
            while True:
                if await request.is_disconnected():
                    break
                payload = await asyncio.to_thread(_dashboard_event, pipeline, learning)
                yield f"event: dashboard\ndata: {json.dumps(payload)}\n\n"
                if once:
                    break
                await asyncio.sleep(_BROADCAST_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.debug("Dashboard SSE cancelled")
            raise

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
