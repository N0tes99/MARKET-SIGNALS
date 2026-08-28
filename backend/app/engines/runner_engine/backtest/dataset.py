"""Labeled Radar study universe — research / benchmarking, not recommendations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.engines.runner_engine.types import DimensionScore

# Pattern studies from the Phase 5 brief. Live labels come from the price path.
PATTERN_STUDY_SYMBOLS: tuple[str, ...] = (
    "NBIS",
    "SMCI",
    "CRDO",
    "ALAB",
    "AAOI",
    "LITE",
    "CLS",
    "VRT",
)

# Staples used as a false-positive denominator — not a prediction they cannot 2×.
CONTROL_SYMBOLS: tuple[str, ...] = ("KO", "JNJ")

STUDY_SYMBOLS: tuple[str, ...] = PATTERN_STUDY_SYMBOLS + CONTROL_SYMBOLS

# Extra names fetched so relative strength is truncated at the same as-of.
STUDY_BENCHMARKS: tuple[str, ...] = ("SPY", "SMH")

OFFSET_DAYS: tuple[int, ...] = (180, 90, 60, 30, 10, 0)
MULTIPLES: tuple[int, ...] = (2, 3, 5, 10)


@dataclass(frozen=True)
class DatedFundamentals:
    """Point-in-time fundamental/catalyst dims. Ignored when as_of is after the bar."""

    as_of: date
    dimensions: dict[str, DimensionScore] = field(default_factory=dict)
