"""Composite Runner Score + explainability helpers."""

from __future__ import annotations

import logging

from app.engines.runner_engine.config import RunnerConfig
from app.engines.runner_engine.types import DataQuality, DimensionScore, RunnerScores
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)


def _scale(score: float, low: float, high: float) -> float:
    """Map 0–100 score into multiplicative band [low, high]."""
    t = clamp_score(score) / 100.0
    return low + (high - low) * t


def compose_runner_scores(
    dimensions: dict[str, DimensionScore],
    config: RunnerConfig,
) -> RunnerScores:
    """Build RunnerScores from dimension outputs.

    Core = product of scaled Fundamental × Catalyst × Structure × Asymmetry.
    Then add weighted modifiers and subtract penalties (Phase 1: penalties=0).
    """
    f = dimensions["fundamental"].score
    c = dimensions["catalyst"].score
    s = dimensions["structure"].score
    a = dimensions["asymmetry"].score
    gap = dimensions["discovery_gap"].score
    theme = dimensions["theme_bottleneck"].score
    inst = dimensions["institutional_accum"].score
    si = dimensions["short_squeeze_potential"].score

    low, high = config.core_scale_low, config.core_scale_high
    core = (
        _scale(f, low, high)
        * _scale(c, low, high)
        * _scale(s, low, high)
        * _scale(a, low, high)
    )
    # Geometric mean-ish normalization so core≈1.0 maps near mid score
    # four factors at 0.75 mid-scale → product ~0.316; map via root
    core_norm = core ** 0.25 if core > 0 else 0.0
    base = clamp_score(core_norm * 100.0)

    w = config.weights
    # Modifier contribution: (dim - 50) * weight, clipped
    modifiers = (
        w.discovery_gap * (gap - 50.0)
        + w.theme_bottleneck * (theme - 50.0)
        + w.institutional_accum * (inst - 50.0)
        + w.short_squeeze * (si - 50.0)
    )
    penalties = 0.0
    runner = clamp_score(base + modifiers - penalties)

    # Risk stays separate: Phase 1 baseline elevated when data missing
    missing = sum(1 for d in dimensions.values() if d.data_quality == "missing")
    risk = clamp_score(40.0 + missing * 4.0)

    scores = RunnerScores(
        fundamental=clamp_score(f),
        catalyst=clamp_score(c),
        structure=clamp_score(s),
        asymmetry=clamp_score(a),
        discovery_gap=clamp_score(gap),
        theme_bottleneck=clamp_score(theme),
        institutional_accum=clamp_score(inst),
        short_squeeze_potential=clamp_score(si),
        runner_score=runner,
        risk_score=risk,
        penalties=penalties,
    )
    logger.info(
        "runner_compose core=%.4f core_norm=%.4f base=%.1f modifiers=%.2f "
        "runner=%.1f risk=%.1f",
        core,
        core_norm,
        base,
        modifiers,
        runner,
        risk,
    )
    return scores


def aggregate_data_quality(dimensions: dict[str, DimensionScore]) -> DataQuality:
    """Worst-case quality across dimensions."""
    qualities = {d.data_quality for d in dimensions.values()}
    if "missing" in qualities:
        return "missing"
    if "degraded" in qualities:
        return "degraded"
    return "good"


def collect_explainability(
    dimensions: dict[str, DimensionScore],
) -> tuple[list[str], list[str], list[str]]:
    """Merge factors, conflicts, and risk flags from dimensions."""
    factors: list[str] = []
    conflicts: list[str] = []
    risk_flags: list[str] = []
    for dim in dimensions.values():
        for item in dim.factors:
            labeled = f"[{dim.name}] {item}"
            if labeled not in factors:
                factors.append(labeled)
        for item in dim.conflicts:
            labeled = f"[{dim.name}] {item}"
            if labeled not in conflicts:
                conflicts.append(labeled)
        if dim.data_quality == "missing":
            flag = f"Missing data: {dim.name}"
            if flag not in risk_flags:
                risk_flags.append(flag)
    return factors, conflicts, risk_flags


def confidence_from_dimensions(dimensions: dict[str, DimensionScore]) -> float:
    """Mean dimension confidence, clamped."""
    if not dimensions:
        return 0.0
    avg = sum(d.confidence for d in dimensions.values()) / len(dimensions)
    return clamp_score(avg * 100.0 if avg <= 1.5 else avg)
