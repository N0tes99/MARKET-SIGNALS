"""Public teaser endpoints for unauthenticated surfaces (login preview)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.routes import assets as assets_routes
from app.core.service_dependencies import get_paper_agent
from app.engines.paper_agent.agent import PaperAgent
from app.schemas.assets import AssetSummary
from app.schemas.paper import PaperLedgerSchema

router = APIRouter(prefix="/public", tags=["public"])


class PublicPreviewSchema(BaseModel):
    """Compact engine snapshot for the login / marketing surfaces."""

    as_of: datetime
    hot_picks: list[AssetSummary] = Field(default_factory=list)
    optimistic: PaperLedgerSchema
    honest: PaperLedgerSchema
    paper_as_of: datetime | None = None
    last_tick_at: datetime | None = None


def _hot_picks(limit: int = 5) -> list[AssetSummary]:
    """Serve ranked symbols from memory/disk only — never block on cold rank_all."""
    cached = assets_routes._ASSETS_LIST_CACHE.get("dashboard", allow_stale=True)
    if not cached:
        cached = assets_routes._read_durable_summaries() or []
    ranked = sorted(
        cached,
        key=lambda a: (a.confidence, a.expected_value),
        reverse=True,
    )
    return ranked[:limit]


def _build_preview(agent: PaperAgent) -> PublicPreviewSchema:
    summary = agent.summary(tick_notes=[])
    return PublicPreviewSchema(
        as_of=datetime.now(UTC),
        hot_picks=_hot_picks(5),
        optimistic=PaperLedgerSchema(**summary.optimistic.__dict__),
        honest=PaperLedgerSchema(**summary.honest.__dict__),
        paper_as_of=summary.as_of,
        last_tick_at=summary.last_tick_at,
    )


@router.get("/preview", response_model=PublicPreviewSchema)
async def public_preview(
    agent: PaperAgent = Depends(get_paper_agent),
) -> PublicPreviewSchema:
    """Login-screen teaser: hot picks + paper bot ledgers (no MFA required)."""
    return await asyncio.to_thread(_build_preview, agent)
