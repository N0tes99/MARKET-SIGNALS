"""Surface 5 — Market Expansion Detection Engine (benchmark MVP)."""

from app.engines.expansion_engine.scanner import ExpansionScanner, scan_expansion_feed
from app.engines.expansion_engine.types import ExpansionCandidate, ExpansionState

__all__ = [
    "ExpansionCandidate",
    "ExpansionScanner",
    "ExpansionState",
    "scan_expansion_feed",
]
