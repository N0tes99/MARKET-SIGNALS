"""WebSocket live dashboard updates."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.tracked import TRACKED_SYMBOLS
from app.core.service_dependencies import get_decision_pipeline
from app.services.decision_pipeline import DecisionPipelineService

logger = logging.getLogger(__name__)

router = APIRouter()

_TRACKED_ASSETS = list(TRACKED_SYMBOLS)
_BROADCAST_INTERVAL_SECONDS = 30


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    """Stream live asset summaries to connected dashboard clients."""
    await websocket.accept()
    pipeline = get_decision_pipeline()

    try:
        while True:
            payload = _build_dashboard_payload(pipeline)
            await websocket.send_text(json.dumps(payload))
            await asyncio.sleep(_BROADCAST_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.debug("Dashboard WebSocket client disconnected")
    except Exception:
        logger.exception("Dashboard WebSocket error")
        await websocket.close()


def _build_dashboard_payload(pipeline: DecisionPipelineService) -> dict:
    """Build a JSON-serializable dashboard update."""
    decisions = pipeline.rank_all(_TRACKED_ASSETS)
    return {
        "type": "dashboard_update",
        "assets": [
            {
                "symbol": d.symbol,
                "confidence": d.evidence.total_confidence,
                "trade_grade": d.opportunity.trade_grade,
                "trade_state": d.trade_state.value,
                "execution_signal": d.execution.signal.value,
                "expected_value": d.opportunity.expected_value,
                "summary": d.summary,
            }
            for d in decisions
        ],
    }
