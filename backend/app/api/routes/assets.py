"""Asset dashboard endpoints."""

import asyncio
import logging
import os
from pathlib import Path
from threading import Lock, Thread

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter

from app.api.tracked import TRACKED_SYMBOLS, is_tracked
from app.core.service_dependencies import (
    get_alert_service,
    get_decision_pipeline,
    get_learning_engine,
)
from app.engines.learning_engine import LearningEngine
from app.market_data.freshness import freshness_tracker
from app.market_data.symbols import get_asset_class
from app.schemas.assets import AssetSummary
from app.services.alert_service import AlertService
from app.services.decision_pipeline import DecisionPipelineService
from app.utils.disk_cache import read_json, write_json
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

router = APIRouter()

_ASSETS_LIST_CACHE: TTLCache[list[AssetSummary]] = TTLCache(ttl_seconds=120.0)
_ASSET_SUMMARY_LIST = TypeAdapter(list[AssetSummary])
_DISK_CACHE_PATH = Path(
    os.environ.get("ASSETS_DISK_CACHE_PATH", "/tmp/se_assets_dashboard.json")
)
_REDDIT_WARM_LOCK = Lock()
_REDDIT_WARM_STARTED = False


def _kick_reddit_warm() -> None:
    """Background-fill Reddit caches so ranking can pick them up next cycle."""
    global _REDDIT_WARM_STARTED
    with _REDDIT_WARM_LOCK:
        if _REDDIT_WARM_STARTED:
            return
        _REDDIT_WARM_STARTED = True

    def _run() -> None:
        try:
            from app.config import settings
            from app.market_data.providers.reddit_public import prefetch_reddit_buzz

            if not settings.reddit_social_enabled:
                return
            result = prefetch_reddit_buzz(list(TRACKED_SYMBOLS))
            logger.info("Background Reddit warm: %s", result)
        except Exception:
            logger.exception("Background Reddit warm failed")

    Thread(target=_run, name="reddit-warm", daemon=True).start()


def _score_for_category(decision, category: str) -> float:
    """Extract category score from decision evidence."""
    for item in decision.evidence.items:
        if item.category == category:
            return item.score
    return 0.0


def _trend_label(trend_score: float) -> str:
    """Map trend score to direction label."""
    if trend_score == 0.0:
        return "Neutral"
    if trend_score >= 60:
        return "Bullish"
    if trend_score <= 40:
        return "Bearish"
    return "Neutral"


def _build_summary(decision) -> AssetSummary:
    """Build dashboard summary from a pipeline decision."""
    trend_score = _score_for_category(decision, "Trend")
    snap = freshness_tracker.status(decision.symbol)
    return AssetSummary(
        symbol=decision.symbol,
        confidence=decision.evidence.total_confidence,
        trend=_trend_label(trend_score),
        trade_grade=decision.opportunity.trade_grade,
        buyer_strength=_score_for_category(decision, "Momentum"),
        risk=_score_for_category(decision, "Risk"),
        expected_value=decision.opportunity.expected_value,
        trade_state=decision.trade_state.value,
        execution_signal=decision.execution.signal.value,
        asset_class=get_asset_class(decision.symbol).value,
        data_degraded=snap.degraded,
        data_age_seconds=snap.age_seconds,
        data_stale_reason=snap.reason,
    )


def _record_decisions(learning: LearningEngine, decisions) -> None:
    """Store pipeline decisions for learning and similarity."""
    for decision in decisions:
        learning.record_decision(decision)


def _load_asset_summaries(
    pipeline: DecisionPipelineService,
    learning: LearningEngine,
) -> list[AssetSummary]:
    """Rank all tracked assets and build dashboard summaries."""
    decisions = pipeline.rank_all(list(TRACKED_SYMBOLS))
    _record_decisions(learning, decisions)
    assets = [_build_summary(d) for d in decisions]
    write_json(_DISK_CACHE_PATH, _ASSET_SUMMARY_LIST.dump_python(assets, mode="json"))
    return assets


def _read_disk_summaries() -> list[AssetSummary] | None:
    """Reload last successful dashboard payload from disk (survives restarts)."""
    raw = read_json(_DISK_CACHE_PATH)
    if raw is None:
        return None
    try:
        return _ASSET_SUMMARY_LIST.validate_python(raw)
    except Exception:
        logger.exception("Invalid assets disk cache at %s", _DISK_CACHE_PATH)
        return None


def _get_dashboard_assets(
    pipeline: DecisionPipelineService,
    learning: LearningEngine,
) -> list[AssetSummary]:
    """Memory SWR first; seed from disk on cold miss so Netlify never waits on rank_all."""
    def factory() -> list[AssetSummary]:
        return _load_asset_summaries(pipeline, learning)

    if _ASSETS_LIST_CACHE.get("dashboard", allow_stale=True) is not None:
        return _ASSETS_LIST_CACHE.get_stale_while_revalidate("dashboard", factory)

    disk = _read_disk_summaries()
    if disk:
        _ASSETS_LIST_CACHE.seed_stale("dashboard", disk)
        return _ASSETS_LIST_CACHE.get_stale_while_revalidate("dashboard", factory)

    return _ASSETS_LIST_CACHE.get_stale_while_revalidate("dashboard", factory)


@router.get("", response_model=list[AssetSummary])
async def list_assets(
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
    learning: LearningEngine = Depends(get_learning_engine),
    alerts: AlertService = Depends(get_alert_service),
) -> list[AssetSummary]:
    """Return summary metrics for all tracked dashboard assets (SWR ~120s + disk)."""
    _kick_reddit_warm()
    assets = await asyncio.to_thread(_get_dashboard_assets, pipeline, learning)

    # Don't block the response on Discord/email dispatch
    async def _dispatch() -> None:
        try:
            await asyncio.to_thread(alerts.dispatch, assets)
        except Exception:
            logger.exception("Alert dispatch failed")

    asyncio.create_task(_dispatch())
    return assets


@router.get("/{symbol}", response_model=AssetSummary)
async def get_asset(
    symbol: str,
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> AssetSummary:
    """Return summary metrics for a single asset."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    decision = await asyncio.to_thread(pipeline.evaluate, normalized)
    return _build_summary(decision)
