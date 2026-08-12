"""Central API router aggregating all route modules."""

from fastapi import APIRouter

from app.api.routes import (
    alerts,
    analysis,
    assets,
    auth,
    backtests,
    decision,
    equity_setups,
    evidence,
    evidence_snapshots,
    favorites,
    health,
    learning,
    opportunities,
    paper,
    public_preview,
    quotes,
    setups,
    social,
    ticker_requests,
    tuning,
    wallet_auth,
    websocket,
)
from app.core.site_gate import router as site_gate_router

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(public_preview.router, tags=["public"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(wallet_auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(site_gate_router, prefix="/auth", tags=["auth"])
api_router.include_router(social.router, tags=["social"])
api_router.include_router(favorites.router, prefix="/me/favorites", tags=["favorites"])
api_router.include_router(
    ticker_requests.router, prefix="/ticker-requests", tags=["ticker-requests"]
)
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(quotes.router, prefix="/quotes", tags=["quotes"])
api_router.include_router(decision.router, prefix="/assets", tags=["decision"])
api_router.include_router(analysis.router, prefix="/assets", tags=["analysis"])
api_router.include_router(learning.router, prefix="/assets", tags=["learning"])
api_router.include_router(evidence.router, prefix="/assets", tags=["evidence"])
api_router.include_router(setups.router, prefix="/assets", tags=["setups"])
api_router.include_router(setups.feed_router, prefix="/setups", tags=["setups"])
api_router.include_router(equity_setups.router, prefix="/assets", tags=["equity-setups"])
api_router.include_router(
    equity_setups.feed_router, prefix="/equity-setups", tags=["equity-setups"]
)
api_router.include_router(evidence_snapshots.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
api_router.include_router(paper.router, prefix="/paper", tags=["paper"])
api_router.include_router(backtests.router, prefix="/backtests", tags=["backtests"])
api_router.include_router(tuning.router, prefix="/tuning", tags=["tuning"])
api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
