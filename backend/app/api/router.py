"""Central API router aggregating all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    alerts,
    analysis,
    assets,
    backtests,
    decision,
    evidence,
    evidence_snapshots,
    health,
    learning,
    opportunities,
    quotes,
    tuning,
    websocket,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(decision.router, prefix="/assets", tags=["decision"])
api_router.include_router(analysis.router, prefix="/assets", tags=["analysis"])
api_router.include_router(learning.router, prefix="/assets", tags=["learning"])
api_router.include_router(evidence.router, prefix="/assets", tags=["evidence"])
api_router.include_router(evidence_snapshots.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
api_router.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
api_router.include_router(tuning.router, prefix="/tuning", tags=["tuning"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
