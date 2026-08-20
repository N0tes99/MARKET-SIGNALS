"""Chart screenshot analysis endpoint."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status

from app.api.tracked import is_tracked
from app.core.auth_deps import get_chart_user
from app.core.rate_limit import limit_chart_analysis
from app.core.service_dependencies import get_chart_analyzer, get_decision_pipeline
from app.engines.ai_engine.chart_analyzer import (
    ChartAnalyzer,
    VisionUnavailable,
    attach_decision,
    normalize_symbol_hint,
)
from app.engines.ai_engine.engine import get_llm_backend
from app.engines.ai_engine.image import MAX_UPLOAD_BYTES, ImageRejected, prepare_chart_image
from app.models.user import User
from app.schemas.chart_analysis import ChartAnalysisSchema, ChartAnalysisStatusSchema
from app.services.decision_pipeline import DecisionPipelineService, DecisionResult

logger = logging.getLogger(__name__)

router = APIRouter()

_STATUS_HINTS = {
    "groq": "Groq vision is on. A screenshot scan usually takes 15–45 seconds.",
    "local": (
        "No Groq key. Enter a tracked ticker — desk engines still map "
        "WAIT / WATCH / EXECUTE."
    ),
}


@router.get("/status", response_model=ChartAnalysisStatusSchema)
async def chart_analysis_status(
    _user: User | None = Depends(get_chart_user),
) -> ChartAnalysisStatusSchema:
    """Report whether screenshot vision is configured."""
    backend = get_llm_backend()
    source = backend[2] if backend is not None else "local"
    return ChartAnalysisStatusSchema(
        vision=backend is not None,
        source=source,
        hint=_STATUS_HINTS.get(source, _STATUS_HINTS["local"]),
    )


@router.post("", response_model=ChartAnalysisSchema)
async def analyze_chart_screenshot(
    request: Request,
    file: UploadFile | None = File(None, description="Chart or trade screenshot"),
    note: str = Form("", max_length=500),
    symbol_hint: str = Form("", max_length=16),
    user: User | None = Depends(get_chart_user),
    analyzer: ChartAnalyzer = Depends(get_chart_analyzer),
    pipeline: DecisionPipelineService = Depends(get_decision_pipeline),
) -> ChartAnalysisSchema:
    """Read a chart screenshot and return possible positions with a thesis.

    Groq vision reads the screenshot when GROQ_API_KEY is set. Without a key,
    pass a tracked symbol and the decision pipeline still navigates
    WAIT / WATCH / EXECUTE.
    """
    limit_chart_analysis(request, str(user.id) if user is not None else "anon")

    hint = normalize_symbol_hint(symbol_hint)
    has_upload = bool(file is not None and file.filename)
    if not has_upload and not hint:
        raise HTTPException(
            status_code=400,
            detail="Upload a screenshot or enter a tracked symbol (BTC, NVDA, …).",
        )

    image = None
    if has_upload and file is not None:
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
        logger.exception("Chart analysis failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis failed. Retry shortly.",
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
