"""Opportunity Engine — ranks every asset; setup scanner is a second surface."""

from app.engines.opportunity_engine.engine import OpportunityEngine, OpportunityResult
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.opportunity_engine.types import OpportunityIdea
from app.scoring.grading import TradeState

__all__ = [
    "OpportunityEngine",
    "OpportunityIdea",
    "OpportunityResult",
    "SetupScanner",
    "TradeState",
]
