"""WebSocket live dashboard updates."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.routes.assets import _get_dashboard
from app.core.basic_auth import auth_enabled
from app.core.security import SESSION_COOKIE_NAME, decode_session_claims
from app.core.site_gate import (
    MFA_COOKIE_NAME,
    cookie_session_has_access,
    decode_mfa_token,
    gate_enabled,
)
from app.database.session import async_session_factory
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()

_BROADCAST_INTERVAL_SECONDS = 30
# Custom close code: unauthenticated (HTTP 401 analogue). Not a standard RFC code.
_WS_UNAUTHORIZED = 4401


async def _websocket_authorized(websocket: WebSocket) -> bool:
    """Match HTTP: login + grant + MFA when the site gate is on."""
    if not auth_enabled() and not gate_enabled():
        return True
    session_tok = websocket.cookies.get(SESSION_COOKIE_NAME)
    claims = decode_session_claims(session_tok) if session_tok else None
    if claims is None:
        return False
    if not gate_enabled():
        try:
            async with async_session_factory() as session:
                user = await session.get(User, claims.user_id)
            if user is None:
                return False
            return int(user.session_version or 0) == claims.session_version
        except Exception:
            logger.exception("WebSocket session lookup failed")
            return False
    mfa = websocket.cookies.get(MFA_COOKIE_NAME)
    if not decode_mfa_token(
        mfa, user_id=claims.user_id, session_version=claims.session_version
    ):
        return False
    try:
        async with async_session_factory() as session:
            denied = await cookie_session_has_access(
                session,
                claims.user_id,
                session_version=claims.session_version,
            )
        return denied is None
    except Exception:
        logger.exception("WebSocket grant lookup failed")
        return False


@router.websocket("/dashboard")
async def dashboard_websocket(websocket: WebSocket) -> None:
    """Stream the GET /assets payload. Prefer SSE through the Netlify proxy.

    Unauthenticated upgrades are rejected with close code 4401 when login or
    the site gate is required.
    """
    if not await _websocket_authorized(websocket):
        await websocket.close(code=_WS_UNAUTHORIZED, reason="Login required")
        return

    await websocket.accept()

    try:
        while True:
            dashboard = _get_dashboard(sync=False)
            await websocket.send_text(
                json.dumps(dashboard.model_dump(mode="json"))
            )
            await asyncio.sleep(_BROADCAST_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.debug("Dashboard WebSocket client disconnected")
    except Exception:
        logger.exception("Dashboard WebSocket error")
        await websocket.close()
