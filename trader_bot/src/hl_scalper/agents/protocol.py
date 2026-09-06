"""Multi-agent execution desk — no single specialist can force a trade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from hl_scalper.feed import L2Book
from hl_scalper.strategy import Side, Signal

ProposalKind = Literal["enter", "sit_out", "abstain", "veto"]


@dataclass(frozen=True)
class MarketSnapshot:
    """Shared world-state each agent sees for one coin/tick."""

    book: L2Book
    funding: float | None = None  # HL hourly-style funding decimal
    premium: float | None = None
    mark_px: float | None = None
    open_interest: float | None = None


@dataclass(frozen=True)
class Proposal:
    agent: str
    kind: ProposalKind
    side: Side | None = None
    confidence: float = 0.0  # 0–100
    reason: str = ""
    signal: Signal | None = None


@dataclass
class DeskDecision:
    action: Literal["enter", "sit_out"]
    side: Side | None = None
    signal: Signal | None = None
    reason: str = ""
    proposals: list[Proposal] = field(default_factory=list)
    agreeing_agents: list[str] = field(default_factory=list)


class SpecialistAgent(Protocol):
    name: str

    def propose(self, snap: MarketSnapshot) -> Proposal: ...
