"""Asset dashboard endpoints."""

import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import TypeAdapter

from app.api.tracked import TRACKED_SYMBOLS, is_tracked
from app.core.rate_limit import limit_heavy_compute
from app.core.service_dependencies import (
    get_alert_service,
    get_decision_pipeline,
    get_learning_engine,
)
from app.engines.learning_engine import LearningEngine
from app.market_data.freshness import freshness_tracker
from app.market_data.symbols import get_asset_class
from app.schemas.assets import AssetsDashboard, AssetSummary, RankingStatus
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
# Postgres paper_agent_state key — /tmp is ephemeral on Render free.
DASHBOARD_META_KEY = "dashboard_assets_v1"
_REDDIT_WARM_LOCK = Lock()
_REDDIT_WARM_STARTED = False
_DASHBOARD_STORE_LOCK = Lock()
_DASHBOARD_STORE = None


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


def _dashboard_kv_store():
    """Lazy paper-store handle for durable ranking JSON (process-local)."""
    global _DASHBOARD_STORE
    with _DASHBOARD_STORE_LOCK:
        if _DASHBOARD_STORE is None:
            from app.engines.paper_agent.factory import build_paper_store

            _DASHBOARD_STORE = build_paper_store()
        return _DASHBOARD_STORE


def _parse_summaries(raw) -> list[AssetSummary] | None:
    if raw is None:
        return None
    try:
        return _ASSET_SUMMARY_LIST.validate_python(raw)
    except Exception:
        logger.exception("Invalid assets dashboard payload")
        return None


def _persist_summaries(assets: list[AssetSummary]) -> None:
    """Write ranking snapshot to /tmp and Postgres so cold starts stay seeded."""
    payload = _ASSET_SUMMARY_LIST.dump_python(assets, mode="json")
    write_json(_DISK_CACHE_PATH, payload)
    try:
        store = _dashboard_kv_store()
        set_meta = getattr(store, "set_meta", None)
        if callable(set_meta):
            set_meta(DASHBOARD_META_KEY, json.dumps(payload, default=str))
    except Exception:
        logger.debug("Durable dashboard seed write skipped", exc_info=True)


def _resolve_dep(request: Request | None, dependency, fallback):
    """Honor FastAPI test overrides when the route no longer Depends() the service."""
    if request is not None:
        override = request.app.dependency_overrides.get(dependency)
        if override is not None:
            return override()
    return fallback()


def _load_asset_summaries(
    pipeline: DecisionPipelineService,
    learning: LearningEngine,
) -> list[AssetSummary]:
    """Rank all tracked assets and build dashboard summaries."""
    decisions = pipeline.rank_all(list(TRACKED_SYMBOLS))
    _record_decisions(learning, decisions)
    assets = [_build_summary(d) for d in decisions]
    _persist_summaries(assets)
    return assets


def _read_disk_summaries() -> list[AssetSummary] | None:
    """Reload last successful dashboard payload from disk (survives restarts)."""
    return _parse_summaries(read_json(_DISK_CACHE_PATH))


def _read_durable_summaries() -> list[AssetSummary] | None:
    """Disk first, then Postgres paper_agent_state (Render /tmp is wiped on sleep)."""
    disk = _read_disk_summaries()
    if disk:
        return disk
    try:
        store = _dashboard_kv_store()
        get_meta = getattr(store, "get_meta", None)
        if not callable(get_meta):
            return None
        raw = get_meta(DASHBOARD_META_KEY)
        if not raw:
            return None
        return _parse_summaries(json.loads(raw))
    except Exception:
        logger.debug("Durable dashboard seed read skipped", exc_info=True)
        return None


def _ranking_status(*, fresh: bool, refreshing: bool, assets: list[AssetSummary]) -> RankingStatus:
    if refreshing or not assets:
        return "warming"
    if fresh:
        return "fresh"
    return "stale"


def _get_dashboard(
    *,
    sync: bool = False,
    request: Request | None = None,
) -> AssetsDashboard:
    """Memory SWR + disk seed; cold miss never blocks unless ``sync=True``.

    Pipeline construction is deferred until a rank is actually needed so a
    Postgres-seeded dashboard can return before scanners boot.
    """

    def factory() -> list[AssetSummary]:
        pipeline = _resolve_dep(request, get_decision_pipeline, get_decision_pipeline)
        learning = _resolve_dep(request, get_learning_engine, get_learning_engine)
        return _load_asset_summaries(pipeline, learning)

    if sync:
        assets = factory()
        _ASSETS_LIST_CACHE.set("dashboard", assets)
        return AssetsDashboard(
            assets=assets,
            ranking_status="fresh",
            cache_age_seconds=0.0,
            as_of=datetime.now(UTC),
        )

    cached, _, _, _ = _ASSETS_LIST_CACHE.meta("dashboard")
    if cached is None:
        seed = _read_durable_summaries()
        # Seed stale so SWR returns immediately and refreshes in background.
        # Empty list = true cold start (placeholders on the client until warm).
        _ASSETS_LIST_CACHE.seed_stale("dashboard", seed if seed else [])

    assets = _ASSETS_LIST_CACHE.get_stale_while_revalidate("dashboard", factory)
    _, fresh, refreshing, age = _ASSETS_LIST_CACHE.meta("dashboard")
    status = _ranking_status(fresh=fresh, refreshing=refreshing, assets=assets)
    return AssetsDashboard(
        assets=assets,
        ranking_status=status,
        cache_age_seconds=age,
        as_of=datetime.now(UTC),
    )


@router.get("", response_model=AssetsDashboard)
async def list_assets(
    request: Request,
    sync: bool = False,
    alerts: AlertService = Depends(get_alert_service),
) -> AssetsDashboard:
    """Return tracked asset summaries with progressive ranking metadata.

    Default: serve memory/disk snapshots immediately; cold miss kicks
    ``rank_all`` in a background thread (avoids Netlify proxy 504s).

    ``sync=true``: block until a full rank completes (keep-warm / tests).
    """
    if sync:
        limit_heavy_compute(request)
    dashboard = await asyncio.to_thread(_get_dashboard, sync=sync, request=request)
    _kick_reddit_warm()

    # Don't block the response on Discord/email dispatch
    async def _dispatch() -> None:
        try:
            await asyncio.to_thread(alerts.dispatch, dashboard.assets)
        except Exception:
            logger.exception("Alert dispatch failed")

    if dashboard.assets:
        asyncio.create_task(_dispatch())
    return dashboard


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
