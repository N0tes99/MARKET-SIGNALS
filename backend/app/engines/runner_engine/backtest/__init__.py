"""Radar structure-tape backtest (Phase 5) and OOS threshold tune (Phase 6)."""

from app.engines.runner_engine.backtest.dataset import (
    HOLDOUT_STUDY_SYMBOLS,
    PATTERN_STUDY_SYMBOLS,
    STUDY_SYMBOLS,
    TRAIN_STUDY_SYMBOLS,
    DatedFundamentals,
)
from app.engines.runner_engine.backtest.replay import evaluate_as_of
from app.engines.runner_engine.backtest.study import (
    LeadTimeStudy,
    cached_live_study,
    run_study,
)
from app.engines.runner_engine.backtest.tune import (
    TuneReport,
    cached_live_tune,
    run_tune,
)

__all__ = [
    "DatedFundamentals",
    "HOLDOUT_STUDY_SYMBOLS",
    "LeadTimeStudy",
    "PATTERN_STUDY_SYMBOLS",
    "STUDY_SYMBOLS",
    "TRAIN_STUDY_SYMBOLS",
    "TuneReport",
    "cached_live_study",
    "cached_live_tune",
    "evaluate_as_of",
    "run_study",
    "run_tune",
]
