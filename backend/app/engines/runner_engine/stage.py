"""Stage 0–7 and signal-type classification for Runner Detection."""

from __future__ import annotations

import logging

from app.engines.runner_engine.config import RunnerConfig, StageThresholds
from app.engines.runner_engine.types import (
    RunnerScores,
    RunnerSignalType,
    RunnerStage,
    WatchlistBucket,
)

logger = logging.getLogger(__name__)


def classify_stage(scores: RunnerScores, thresholds: StageThresholds) -> RunnerStage:
    """Map score breakdown to the furthest justified stage (prioritize 1→4)."""
    f = scores.fundamental
    c = scores.catalyst
    s = scores.structure
    gap = scores.discovery_gap

    # Stage 7 — extended: aggressive structure + discovery largely closed
    if s >= thresholds.extended_structure and gap <= thresholds.extended_discovery_gap_max:
        return "extended"

    # Stage 6 — momentum: strong structure, gap compressing
    if s >= thresholds.momentum_structure and gap <= thresholds.discovery_gap_low + 10:
        return "momentum"

    # Stage 5 — discovery: ignition-level structure with gap closing
    if (
        s >= thresholds.ignition_structure
        and gap <= thresholds.discovery_gap_low
        and f >= thresholds.fundamental_inflection
    ):
        return "discovery"

    # Stage 4 — ignition
    if s >= thresholds.ignition_structure and (
        c >= thresholds.catalyst or f >= thresholds.fundamental_inflection
    ):
        return "ignition"

    # Stage 3 — catalyst present with fundamental support
    if c >= thresholds.catalyst and f >= thresholds.fundamental_inflection:
        return "catalyst"

    # Stage 2 — early accumulation
    if (
        f >= thresholds.fundamental_inflection
        and s >= thresholds.structure_accumulation
    ):
        return "early_accumulation"

    # Stage 1 — fundamental inflection only
    if f >= thresholds.fundamental_inflection:
        return "fundamental_inflection"

    return "dormant"


def classify_signal(
    stage: RunnerStage,
    scores: RunnerScores,
    *,
    has_severe_risk: bool = False,
) -> RunnerSignalType:
    """Derive signal type from stage + scores."""
    if has_severe_risk and stage in {"ignition", "discovery", "momentum"}:
        return "runner_failure"

    mapping: dict[RunnerStage, RunnerSignalType] = {
        "dormant": "none",
        "fundamental_inflection": "early_runner",
        "early_accumulation": "accumulation",
        "catalyst": "accumulation",
        "ignition": "ignition",
        "discovery": "confirmed_runner",
        "momentum": "confirmed_runner",
        "extended": "extended_runner",
    }
    return mapping[stage]


def classify_watchlist(stage: RunnerStage, signal: RunnerSignalType) -> WatchlistBucket:
    """Map stage/signal to EARLY / IGNITION / RUNNING lists."""
    if signal in {"early_runner", "accumulation"} or stage in {
        "fundamental_inflection",
        "early_accumulation",
        "catalyst",
    }:
        return "early"
    if signal == "ignition" or stage == "ignition":
        return "ignition"
    if signal in {"confirmed_runner", "extended_runner"} or stage in {
        "discovery",
        "momentum",
        "extended",
    }:
        return "running"
    return "none"


def classify(
    scores: RunnerScores,
    config: RunnerConfig,
    *,
    has_severe_risk: bool = False,
    fundamentals_available: bool = False,
) -> tuple[RunnerStage, RunnerSignalType, WatchlistBucket]:
    """Full classification with logging.

    Until fundamentals are real, only dormant / early_accumulation may emit.
    Ignition and running lists stay empty.
    """
    if not fundamentals_available:
        if scores.structure >= config.stages.structure_accumulation:
            stage: RunnerStage = "early_accumulation"
        else:
            stage = "dormant"
        signal = classify_signal(stage, scores, has_severe_risk=has_severe_risk)
        watchlist = classify_watchlist(stage, signal)
        logger.info(
            "runner_stage structure_only s%.1f → stage=%s signal=%s list=%s",
            scores.structure,
            stage,
            signal,
            watchlist,
        )
        return stage, signal, watchlist

    stage = classify_stage(scores, config.stages)
    signal = classify_signal(stage, scores, has_severe_risk=has_severe_risk)
    watchlist = classify_watchlist(stage, signal)
    logger.info(
        "runner_stage symbol_scores=f%.1f/c%.1f/s%.1f/gap%.1f → stage=%s signal=%s list=%s",
        scores.fundamental,
        scores.catalyst,
        scores.structure,
        scores.discovery_gap,
        stage,
        signal,
        watchlist,
    )
    return stage, signal, watchlist
