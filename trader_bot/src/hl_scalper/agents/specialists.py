from __future__ import annotations

from hl_scalper.agents.protocol import MarketSnapshot, Proposal, SpecialistAgent
from hl_scalper.config import Settings
from hl_scalper.strategy import Signal, StrategyParams, evaluate, notional, spread_bps


def _lean_signal(book, *, side: str, confidence: float, reason: str) -> Signal | None:
    mid = book.mid
    sp = spread_bps(book)
    if mid is None or sp is None:
        return None
    bid_n = notional(book, bids=True, levels=5)
    ask_n = notional(book, bids=False, levels=5)
    total = bid_n + ask_n
    imb = (bid_n / total) if total > 0 else 0.5
    return Signal(
        coin=book.coin,
        side=side,  # type: ignore[arg-type]
        imbalance=imb,
        spread_bps=sp,
        mid=mid,
        edge_score=confidence,
        reason=reason,
    )


class ImbalanceAgent:
    """S1 — L2 book imbalance scalp proposer."""

    name = "imbalance"

    def __init__(self, settings: Settings) -> None:
        self._params = StrategyParams(
            imbalance_min=settings.imbalance_min,
            spread_bps_max=settings.spread_bps_max,
            min_notional=settings.min_notional,
            book_levels=settings.book_levels,
        )

    def propose(self, snap: MarketSnapshot) -> Proposal:
        signal = evaluate(snap.book, self._params)
        if signal is None:
            return Proposal(self.name, "abstain", reason="no_imbalance")
        return Proposal(
            self.name,
            "enter",
            side=signal.side,
            confidence=signal.edge_score,
            reason=signal.reason,
            signal=signal,
        )


class FundingAgent:
    """S3-lite — extreme HL funding as independent directional vote.

    Does not trade alone in the desk: coordinator requires agreement with others.
    """

    name = "funding"

    def __init__(self, *, extreme: float = 0.0001) -> None:
        self.extreme = extreme

    def propose(self, snap: MarketSnapshot) -> Proposal:
        if snap.funding is None:
            return Proposal(self.name, "abstain", reason="no_funding")
        f = snap.funding
        if f >= self.extreme:
            conf = min(100.0, abs(f) / self.extreme * 55.0)
            sig = _lean_signal(snap.book, side="sell", confidence=conf, reason="funding_rich")
            if sig is None:
                return Proposal(self.name, "abstain", reason="funding_no_book")
            return Proposal(
                self.name, "enter", side="sell", confidence=conf, reason="funding_rich", signal=sig
            )
        if f <= -self.extreme:
            conf = min(100.0, abs(f) / self.extreme * 55.0)
            sig = _lean_signal(snap.book, side="buy", confidence=conf, reason="funding_cheap")
            if sig is None:
                return Proposal(self.name, "abstain", reason="funding_no_book")
            return Proposal(
                self.name, "enter", side="buy", confidence=conf, reason="funding_cheap", signal=sig
            )
        return Proposal(self.name, "abstain", reason="funding_mild")


class LiquidityAgent:
    """Quality gate — sit out on thin/wide books; else abstain (pass)."""

    name = "liquidity"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def propose(self, snap: MarketSnapshot) -> Proposal:
        book = snap.book
        spread = spread_bps(book)
        if spread is None or book.mid is None:
            return Proposal(self.name, "sit_out", reason="broken_book")
        if spread > self.settings.spread_bps_max:
            return Proposal(self.name, "sit_out", confidence=80.0, reason="wide_spread")
        bid_n = notional(book, bids=True, levels=self.settings.book_levels)
        ask_n = notional(book, bids=False, levels=self.settings.book_levels)
        if bid_n + ask_n < self.settings.min_notional:
            return Proposal(self.name, "sit_out", confidence=80.0, reason="thin_book")
        total = bid_n + ask_n
        imb = bid_n / total
        if imb >= 0.60:
            sig = _lean_signal(book, side="buy", confidence=40.0, reason="depth_bid_lean")
            if sig is None:
                return Proposal(self.name, "sit_out", reason="broken_book")
            return Proposal(
                self.name, "enter", side="buy", confidence=40.0, reason="depth_bid_lean", signal=sig
            )
        if imb <= 0.40:
            sig = _lean_signal(book, side="sell", confidence=40.0, reason="depth_ask_lean")
            if sig is None:
                return Proposal(self.name, "sit_out", reason="broken_book")
            return Proposal(
                self.name, "enter", side="sell", confidence=40.0, reason="depth_ask_lean", signal=sig
            )
        return Proposal(self.name, "abstain", reason="balanced_ok")


class SpreadMicroAgent:
    """S2-lite — prefers two-sided micro conditions (tight spread)."""

    name = "spread_micro"

    def __init__(self, *, tight_bps: float = 4.0, lean: float = 0.62) -> None:
        self.tight_bps = tight_bps
        self.lean = lean

    def propose(self, snap: MarketSnapshot) -> Proposal:
        spread = spread_bps(snap.book)
        if spread is None or snap.book.mid is None:
            return Proposal(self.name, "abstain", reason="no_spread")
        if spread > self.tight_bps:
            return Proposal(self.name, "abstain", reason="not_tight")
        bid_n = notional(snap.book, bids=True, levels=5)
        ask_n = notional(snap.book, bids=False, levels=5)
        total = bid_n + ask_n
        if total <= 0:
            return Proposal(self.name, "abstain", reason="empty")
        imb = bid_n / total
        conf = max(0.0, 70.0 - spread * 5.0)
        if imb >= self.lean:
            sig = _lean_signal(snap.book, side="buy", confidence=conf, reason="tight_bid_lean")
            if sig is None:
                return Proposal(self.name, "abstain", reason="no_spread")
            return Proposal(
                self.name, "enter", side="buy", confidence=conf, reason="tight_bid_lean", signal=sig
            )
        if imb <= (1.0 - self.lean):
            sig = _lean_signal(snap.book, side="sell", confidence=conf, reason="tight_ask_lean")
            if sig is None:
                return Proposal(self.name, "abstain", reason="no_spread")
            return Proposal(
                self.name, "enter", side="sell", confidence=conf, reason="tight_ask_lean", signal=sig
            )
        return Proposal(self.name, "abstain", reason="tight_but_flat")


_: list[type[SpecialistAgent]] = [ImbalanceAgent, FundingAgent, LiquidityAgent, SpreadMicroAgent]
