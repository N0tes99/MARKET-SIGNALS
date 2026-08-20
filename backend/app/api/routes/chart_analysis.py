"""Chart screenshot analysis endpoint."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.tracked import is_tracked
from app.core.auth_deps import get_current_user
from app.core.rate_limit import limit_chart_analysis
from app.core.service_dependencies import get_chart_analyzer, get_decision_pipeline
from app.engines.ai_engine.chart_analyzer import (
    ChartAnalyzer,
    VisionUnavailable,
    attach_decision,
    normalize_symbol_hint,
)
from app.engines.ai_engine.image import MAX_UPLOAD_BYTES, ImageRejected, prepare_chart_image
from app.models.user import User
from app.schemas.chart_analysis import ChartAnalysisSchema
from app.services.decision_pipeline import DecisionPipelineService, DecisionResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ChartAnalysisSchema)
async def analyze_chart_screenshot(
    request: Request,
    file: UploadFile = File(..., description="Chart or trade screenshot"),
    note: str = Form("", max_length=500),
    symbol_hint: str = Form("", max_length=16),
    user: User = Depends(get_current_user),
    analyzer: ChartAnalyzer = Depends(get_chart_analyzer),
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> ChartAnalysisSchema:
    """Read a chart screenshot and return possible positions with a thesis.

    Vision models explain what is on the image. When the symbol is tracked,
    the decision pipeline grounds execution so the chart cannot override WAIT.
    """
    limit_chart_analysis(request, str(user.id))

    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 8MB)",
        )

    try:
        image = prepare_chart_image(data, file.content_type)
    except ImageRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    hint = normalize_symbol_hint(symbol_hint)
    decision = await asyncio.to_thread(_maybe_decision, pipeline, hint)

    try:
        result = await asyncio.to_thread(
            analyzer.analyze,
            image,
            note=note.strip(),
            symbol_hint=hint or "",
            decision=decision,
        )
    except VisionUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception:
        logger.exception("Chart vision analysis failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Vision model failed to analyze the screenshot. Retry shortly.",
        ) from None

    detected = normalize_symbol_hint(result.reading.symbol)
    if decision is None and detected and is_tracked(detected):
        late = await asyncio.to_thread(_maybe_decision, pipeline, detected)
        if late is not None:
            result = attach_decision(result, late)

    return result


def _maybe_decision(
    pipeline: DecisionPipelineService,
    symbol: str | None,
) -> DecisionResult | None:
    if not symbol or not is_tracked(symbol):
        return None
    try:
        return pipeline.evaluate(symbol)
    except Exception:
        logger.exception("Desk grounding failed for %s", symbol)
        return None
