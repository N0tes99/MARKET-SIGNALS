"""Surface 4 — Runner Detection Engine (10X Radar)."""

from app.engines.runner_engine.config import (
    DEFAULT_SEED_UNIVERSE,
    RunnerConfig,
    default_runner_config,
)
from app.engines.runner_engine.engine import RunnerEngine
from app.engines.runner_engine.scanner import RunnerScanner
from app.engines.runner_engine.types import RunnerCandidate, RunnerScores

__all__ = [
    "DEFAULT_SEED_UNIVERSE",
    "RunnerCandidate",
    "RunnerConfig",
    "RunnerEngine",
    "RunnerScanner",
    "RunnerScores",
    "default_runner_config",
]
