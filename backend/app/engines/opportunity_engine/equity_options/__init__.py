"""Layer 3 — equity options opportunity surface."""

from app.engines.opportunity_engine.equity_options.scanner import (
    EQUITY_UNIVERSE,
    EquityOptionsScanner,
    build_idea_from_momentum,
)
from app.engines.opportunity_engine.equity_options.types import (
    EquityOptionsIdea,
    ExecutionPlan,
    OptionCandidate,
)

__all__ = [
    "EQUITY_UNIVERSE",
    "EquityOptionsIdea",
    "EquityOptionsScanner",
    "ExecutionPlan",
    "OptionCandidate",
    "build_idea_from_momentum",
]
