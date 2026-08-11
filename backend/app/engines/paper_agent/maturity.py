"""Training maturity — when honest paper memory is dense enough for private live."""

from __future__ import annotations

from dataclasses import dataclass

from app.engines.learning_engine.types import SignalOutcome, SignalRecord
from app.engines.paper_agent.types import PaperTrade

# Soft gates for private micro live later — Phase 1 only reports readiness.
TARGET_HONEST_CLOSED = 30
TARGET_MEMORY_OUTCOMES = 20
MAX_DRAWDOWN_PCT = 20.0
MIN_AVG_RETURN_PCT = 0.0


@dataclass
class PaperMaturity:
    """How far the public paper book + learning memory are from a live unlock."""

    honest_closed: int
    memory_outcomes: int
    win_rate: float
    avg_return_pct: float
    expectancy_ok: bool
    max_drawdown_pct: float
    drawdown_ok: bool
    target_honest_closed: int = TARGET_HONEST_CLOSED
    target_memory_outcomes: int = TARGET_MEMORY_OUTCOMES
    score_pct: float = 0.0
    ready_for_private_live: bool = False
    blockers: list[str] | None = None


def _outcome_from_return(ret: float) -> str:
    if ret > 0.05:
        return SignalOutcome.WIN.value
    if ret < -0.05:
        return SignalOutcome.LOSS.value
    return SignalOutcome.BREAKEVEN.value


def map_honest_close_outcome(trade: PaperTrade) -> tuple[str, float | None]:
    """Map a finished paper trade to a learning outcome (honest ledger only)."""
    if trade.honest_return_pct is None:
        return SignalOutcome.NO_TRADE.value, None
    return _outcome_from_return(trade.honest_return_pct), trade.honest_return_pct


def _peak_drawdown_pct(closed: list[PaperTrade], starting_cash: float) -> float:
    if starting_cash <= 0:
        return 0.0
    equity = starting_cash
    peak = starting_cash
    max_dd = 0.0
    ordered = sorted(closed, key=lambda t: t.closed_at or t.signal_at)
    for t in ordered:
        pnl = t.honest_pnl_usd if t.honest_pnl_usd is not None else 0.0
        equity += pnl
        peak = max(peak, equity)
        if peak > 0:
            dd = (peak - equity) / peak * 100.0
            max_dd = max(max_dd, dd)
    return round(max_dd, 2)


def compute_maturity(
    trades: list[PaperTrade],
    *,
    starting_cash: float,
    memory_records: list[SignalRecord],
) -> PaperMaturity:
    """Score training readiness from honest closes + paper_honest learning rows."""
    honest_closed = [
        t
        for t in trades
        if t.status == "closed" and t.honest_return_pct is not None
    ]
    wins = sum(1 for t in honest_closed if (t.honest_return_pct or 0) > 0.05)
    traded = len(honest_closed)
    win_rate = round((wins / traded) * 100.0, 1) if traded else 0.0
    returns = [t.honest_return_pct or 0.0 for t in honest_closed]
    avg_ret = round(sum(returns) / len(returns), 3) if returns else 0.0
    dd = _peak_drawdown_pct(honest_closed, starting_cash)
    drawdown_ok = dd <= MAX_DRAWDOWN_PCT
    expectancy_ok = avg_ret > MIN_AVG_RETURN_PCT if traded else False

    paper_mem = [
        r
        for r in memory_records
        if r.source == "paper_honest" and r.outcome and r.outcome != SignalOutcome.NO_TRADE.value
    ]
    memory_n = len(paper_mem)

    blockers: list[str] = []
    if traded < TARGET_HONEST_CLOSED:
        blockers.append(f"honest_closed:{traded}/{TARGET_HONEST_CLOSED}")
    if memory_n < TARGET_MEMORY_OUTCOMES:
        blockers.append(f"memory_outcomes:{memory_n}/{TARGET_MEMORY_OUTCOMES}")
    if traded and not expectancy_ok:
        blockers.append("expectancy_non_positive")
    if not drawdown_ok:
        blockers.append(f"drawdown:{dd:.1f}%>{MAX_DRAWDOWN_PCT:.0f}%")

    # Progress toward sample density (expectancy/drawdown gate live unlock, not score %).
    sample_score = min(1.0, traded / TARGET_HONEST_CLOSED) * 0.55
    memory_score = min(1.0, memory_n / TARGET_MEMORY_OUTCOMES) * 0.45
    score_pct = round((sample_score + memory_score) * 100.0, 1)
    ready = not blockers

    return PaperMaturity(
        honest_closed=traded,
        memory_outcomes=memory_n,
        win_rate=win_rate,
        avg_return_pct=avg_ret,
        expectancy_ok=expectancy_ok,
        max_drawdown_pct=dd,
        drawdown_ok=drawdown_ok,
        score_pct=score_pct,
        ready_for_private_live=ready,
        blockers=blockers,
    )
