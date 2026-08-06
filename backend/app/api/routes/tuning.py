"""Scoring weight tuning and optimization endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.tracked import is_tracked
from app.core.service_dependencies import get_weight_optimizer
from app.schemas.tuning import (
    ActiveWeightsSchema,
    ApplyPresetSchema,
    PresetResultSchema,
    WeightTuningSchema,
)
from app.scoring.optimizer import WeightOptimizer

router = APIRouter()


@router.get("/weights", response_model=ActiveWeightsSchema)
async def get_active_weights(
    optimizer: WeightOptimizer = Depends(get_weight_optimizer),
) -> ActiveWeightsSchema:
    """Return currently active scoring weights."""
    preset, weights = optimizer.active_weights()
    return ActiveWeightsSchema(
        preset=preset,
        weights={cat.value: w for cat, w in weights.items()},
    )


@router.get("/optimize/{symbol}", response_model=WeightTuningSchema)
async def optimize_weights(
    symbol: str,
    timeframe: str = Query(default="1h"),
    hold_bars: int = Query(default=24, ge=4, le=72),
    signal_threshold: float = Query(default=55.0, ge=40.0, le=90.0),
    optimizer: WeightOptimizer = Depends(get_weight_optimizer),
) -> WeightTuningSchema:
    """Run walk-forward optimization across weight presets."""
    normalized = symbol.upper()
    if not is_tracked(normalized):
        raise HTTPException(status_code=404, detail=f"Asset '{normalized}' is not tracked")

    result = await asyncio.to_thread(
        optimizer.optimize,
        normalized,
        timeframe,
        hold_bars,
        signal_threshold,
    )

    return WeightTuningSchema(
        symbol=result.symbol,
        timeframe=result.timeframe,
        active_preset=result.active_preset,
        active_weights=result.active_weights,
        recommended_preset=result.recommended_preset,
        recommended_weights=result.recommended_weights,
        results=[
            PresetResultSchema(
                preset_name=r.preset_name,
                weights={cat.value: w for cat, w in r.weights.items()},
                total_signals=r.total_signals,
                win_rate=r.win_rate,
                avg_return_pct=r.avg_return_pct,
                score=r.score,
            )
            for r in result.results
        ],
    )


@router.post("/weights/apply", response_model=ActiveWeightsSchema)
async def apply_weight_preset(
    body: ApplyPresetSchema,
    optimizer: WeightOptimizer = Depends(get_weight_optimizer),
) -> ActiveWeightsSchema:
    """Apply a named weight preset to live scoring."""
    try:
        weights = await asyncio.to_thread(optimizer.apply_preset, body.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ActiveWeightsSchema(
        preset=body.preset,
        weights={cat.value: w for cat, w in weights.items()},
    )


@router.post("/weights/reset", response_model=ActiveWeightsSchema)
async def reset_weights(
    optimizer: WeightOptimizer = Depends(get_weight_optimizer),
) -> ActiveWeightsSchema:
    """Restore default scoring weights."""
    await asyncio.to_thread(optimizer.reset)
    preset, weights = optimizer.active_weights()
    return ActiveWeightsSchema(
        preset=preset,
        weights={cat.value: w for cat, w in weights.items()},
    )
