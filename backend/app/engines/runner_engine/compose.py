"""Composite Runner Score + explainability helpers."""

from __future__ import annotations

import logging

from app.engines.runner_engine.config import RunnerConfig
from app.engines.runner_engine.types import DataQuality, DimensionScore, RunnerScores
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)

_CORE = ("fundamental", "catalyst", "structure", "asymmetry")
_MODIFIERS = (
    ("discovery_gap", "discovery_gap"),
    ("theme_bottleneck", "theme_bottleneck"),
    ("institutional_accum", "institutional_accum"),
    ("short_squeeze_potential", "short_squeeze"),
)


def _scale(score: float, low: float, high: float) -> float:
    """Map 0–100 score into multiplicative band [low, high]."""
    t = clamp_score(score) / 100.0
    return low + (high - low) * t


def _filled(dim: DimensionScore) -> bool:
    return dim.data_quality != "missing"


def compose_runner_scores(
    dimensions: dict[str, DimensionScore],
    config: RunnerConfig,
) -> RunnerScores:
    """Build RunnerScores from filled dimensions only.

    Missing stub 50s do not enter the core. Structure-only scans are capped
    so tape cannot print a high Runner Score before fundamentals exist.
    """
    low, high = config.core_scale_low, config.core_scale_high
    filled_core = [name for name in _CORE if _filled(dimensions[name])]

    if filled_core:
        product = 1.0
        for name in filled_core:
            product *= _scale(dimensions[name].score, low, high)
        core_norm = product ** (1.0 / len(filled_core)) if product > 0 else 0.0
        base = clamp_score(core_norm * 100.0)
    else:
        core_norm = 0.0
        base = 0.0

    w = config.weights
    modifiers = 0.0
    weight_map = {
        "discovery_gap": w.discovery_gap,
        "theme_bottleneck": w.theme_bottleneck,
        "institutional_accum": w.institutional_accum,
        "short_squeeze_potential": w.short_squeeze,
    }
    for name, _attr in _MODIFIERS:
        dim = dimensions[name]
        if _filled(dim):
            modifiers += weight_map[name] * (dim.score - 50.0)

    penalties = 0.0
    runner = clamp_score(base + modifiers - penalties)

    fundamentals_ready = _filled(dimensions["fundamental"])
    if not fundamentals_ready:
        runner = min(runner, config.structure_only_cap)

    missing = sum(1 for d in dimensions.values() if d.data_quality == "missing")
    risk = clamp_score(40.0 + missing * 4.0)

    def _reported(name: str) -> float:
        return clamp_score(dimensions[name].score)

    scores = RunnerScores(
        fundamental=_reported("fundamental"),
        catalyst=_reported("catalyst"),
        structure=_reported("structure"),
        asymmetry=_reported("asymmetry"),
        discovery_gap=_reported("discovery_gap"),
        theme_bottleneck=_reported("theme_bottleneck"),
        institutional_accum=_reported("institutional_accum"),
        short_squeeze_potential=_reported("short_squeeze_potential"),
        runner_score=runner,
        risk_score=risk,
        penalties=penalties,
    )
    logger.info(
        "runner_compose filled_core=%s core_norm=%.4f base=%.1f modifiers=%.2f "
        "runner=%.1f risk=%.1f cap=%s",
        filled_core,
        core_norm,
        base,
        modifiers,
        runner,
        risk,
        None if fundamentals_ready else config.structure_only_cap,
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
    """Mean confidence of filled dimensions only."""
    filled = [d for d in dimensions.values() if _filled(d)]
    if not filled:
        return 0.0
    avg = sum(d.confidence for d in filled) / len(filled)
    return clamp_score(avg * 100.0 if avg <= 1.5 else avg)
