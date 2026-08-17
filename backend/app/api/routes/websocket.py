"""WebSocket live dashboard updates."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.tracked import TRACKED_SYMBOLS
from app.core.security import SESSION_COOKIE_NAME, decode_access_token
from app.core.service_dependencies import get_decision_pipeline
from app.core.site_gate import MFA_COOKIE_NAME, decode_mfa_token, gate_enabled
from app.services.decision_pipeline import DecisionPipelineService

logger = logging.getLogger(__name__)

router = APIRouter()

_TRACKED_ASSETS = list(TRACKED_SYMBOLS)
_BROADCAST_INTERVAL_SECONDS = 30
# Custom close code: unauthenticated (HTTP 401 analogue). Not a standard RFC code.
_WS_UNAUTHORIZED = 4401


def _websocket_authorized(websocket: WebSocket) -> bool:
    """Require a session cookie; when the TOTP gate is on, also require MFA."""
    session_tok = websocket.cookies.get(SESSION_COOKIE_NAME)
    user_id = decode_access_token(session_tok) if session_tok else None
    if user_id is None:
        return False
    if not gate_enabled():
        return True
    mfa = websocket.cookies.get(MFA_COOKIE_NAME)
    return decode_mfa_token(mfa, user_id=user_id)


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    """Stream live asset summaries to connected dashboard clients.

    The frontend polls HTTP ``GET /assets`` instead of this socket. Unauthenticated
    upgrades are rejected with close code 4401 (login required); when the site
    gate is enabled, the MFA cookie is required as well.
    """
    if not _websocket_authorized(websocket):
        await websocket.close(code=_WS_UNAUTHORIZED, reason="Login required")
        return

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
