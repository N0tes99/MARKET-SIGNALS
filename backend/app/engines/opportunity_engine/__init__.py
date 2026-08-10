"""Opportunity Engine — ranks every asset; setup scanners are extra surfaces."""

from app.engines.opportunity_engine.engine import OpportunityEngine, OpportunityResult
from app.engines.opportunity_engine.equity_options import EquityOptionsIdea, EquityOptionsScanner
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.opportunity_engine.types import OpportunityIdea
from app.scoring.grading import TradeState

__all__ = [
    "EquityOptionsIdea",
    "EquityOptionsScanner",
    "OpportunityEngine",
    "OpportunityIdea",
    "OpportunityResult",
    "SetupScanner",
    "TradeState",
]
