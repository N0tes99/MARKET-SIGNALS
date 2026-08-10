"""Public paper agent — executes WATCH setups on dual paper ledgers."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.engines.opportunity_engine.equity_options.scanner import EquityOptionsScanner
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.paper_agent.broker import (
    DEFAULT_SIZE_USD,
    last_price,
    next_bar_open_after,
    should_close,
    unrealized_pnl,
    _bps_slip,
)
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import (
    PaperAgentSummary,
    PaperDirection,
    PaperLedgerSnapshot,
    PaperTrade,
)
from app.market_data.service import MarketDataService

logger = logging.getLogger(__name__)

AGENT_NAME = "Signal Engine Paper Agent"
STARTING_CASH = 100_000.0
MIN_CONFIDENCE = 55.0


def _fingerprint(source: str, symbol: str, setup_type: str, direction: str) -> str:
    raw = f"{source}|{symbol.upper()}|{setup_type}|{direction}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _dir(bias: str) -> PaperDirection | None:
    if bias == "long":
        return "long"
    if bias == "short":
        return "short"
    return None


class PaperAgent:
    """Living paper bot: WATCH ideas → dual-ledger fills → public PnL."""

    def __init__(
        self,
        *,
        market_data: MarketDataService,
        crypto_scanner: SetupScanner,
        equity_scanner: EquityOptionsScanner,
        store: PaperTradeStore | None = None,
        starting_cash: float = STARTING_CASH,
        size_usd: float = DEFAULT_SIZE_USD,
    ) -> None:
        self._market = market_data
        self._crypto = crypto_scanner
        self._equity = equity_scanner
        self._store = store or PaperTradeStore()
        self._starting_cash = starting_cash
        self._size_usd = size_usd
        self._last_tick_at: datetime | None = None

    @property
    def store(self) -> PaperTradeStore:
        return self._store

    def tick(self) -> list[str]:
        """Advance the agent once: open new ideas, resolve honest fills, manage exits."""
        notes: list[str] = []
        now = datetime.now(UTC)
        active = self._store.fingerprints_active()

        # --- Crypto Layer 2 ---
        try:
            crypto_ideas = self._crypto.scan_feed(watch_only=True, min_confidence=MIN_CONFIDENCE)
        except Exception:
            logger.exception("Paper agent crypto feed failed")
            crypto_ideas = []
            notes.append("crypto_feed_error")

        for idea in crypto_ideas:
            direction = _dir(idea.direction_bias)
            if direction is None:
                continue
            fp = _fingerprint("crypto_setup", idea.symbol, idea.setup_type, direction)
            if fp in active:
                continue
            trade = self._open_from_signal(
                source="crypto_setup",
                symbol=idea.symbol,
                setup_type=idea.setup_type,
                direction=direction,
                fingerprint=fp,
                confidence=idea.confidence,
                opportunity_score=idea.confidence,
                factors=list(idea.factors[:5]),
                now=now,
            )
            if trade:
                notes.append(f"open:{trade.symbol}:{trade.setup_type}")
                active.add(fp)

        # --- Equity Layer 3 ---
        try:
            equity_ideas = self._equity.scan_feed(
                watch_only=True,
                min_confidence=MIN_CONFIDENCE,
            )
        except Exception:
            logger.exception("Paper agent equity feed failed")
            equity_ideas = []
            notes.append("equity_feed_error")

        for idea in equity_ideas:
            direction = _dir(idea.direction_bias)
            if direction is None:
                continue
            fp = _fingerprint("equity_setup", idea.symbol, idea.setup_type, direction)
            if fp in active:
                continue
            trade = self._open_from_signal(
                source="equity_setup",
                symbol=idea.symbol,
                setup_type=idea.setup_type,
                direction=direction,
                fingerprint=fp,
                confidence=idea.confidence,
                opportunity_score=idea.opportunity_score,
                factors=list(idea.factors[:5]),
                now=now,
            )
            if trade:
                notes.append(f"open:{trade.symbol}:{trade.setup_type}")
                active.add(fp)

        # --- Manage open / pending ---
        for trade in list(self._store.open_or_pending()):
            self._advance_trade(trade, now=now, notes=notes)

        self._last_tick_at = now
        return notes

    def _open_from_signal(
        self,
        *,
        source: str,
        symbol: str,
        setup_type: str,
        direction: PaperDirection,
        fingerprint: str,
        confidence: float,
        opportunity_score: float,
        factors: list[str],
        now: datetime,
    ) -> PaperTrade | None:
        px = last_price(self._market, symbol)
        if px is None or px <= 0:
            logger.info("Paper skip %s — no mark", symbol)
            return None

        opt_entry = _bps_slip(px, direction, entry=True)
        trade = PaperTrade(
            id=str(uuid4()),
            symbol=symbol.upper(),
            source=source,  # type: ignore[arg-type]
            setup_type=setup_type,
            direction=direction,
            fingerprint=fingerprint,
            signal_at=now,
            confidence=confidence,
            opportunity_score=opportunity_score,
            size_usd=self._size_usd,
            status="pending_honest",
            optimistic_entry=opt_entry,
            optimistic_entry_at=now,
            mark_price=px,
            factors=factors,
            notes=(
                f"Optimistic fill @ {opt_entry:.6g} (signal last {px:.6g} + slip). "
                "Honest fill awaits next 15m bar open."
            ),
        )

        # Try honest fill immediately if a later bar already exists (unlikely but fine)
        nxt = next_bar_open_after(self._market, symbol, now)
        if nxt is not None:
            open_px, bar_ts = nxt
            trade.honest_entry = _bps_slip(open_px, direction, entry=True)
            trade.honest_entry_at = bar_ts
            trade.honest_bar_ts = bar_ts
            trade.status = "open"
            trade.notes += f" Honest fill @ {trade.honest_entry:.6g} bar {bar_ts.isoformat()}."

        self._store.upsert(trade)
        logger.info(
            "Paper open %s %s %s conf=%.1f opt=%.6g honest=%s",
            trade.symbol,
            trade.setup_type,
            trade.direction,
            trade.confidence,
            trade.optimistic_entry,
            f"{trade.honest_entry:.6g}" if trade.honest_entry else "pending",
        )
        return trade

    def _advance_trade(self, trade: PaperTrade, *, now: datetime, notes: list[str]) -> None:
        mark = last_price(self._market, trade.symbol) or trade.mark_price
        if mark is None:
            return
        trade.mark_price = mark

        if trade.status == "pending_honest" and trade.honest_entry is None:
            nxt = next_bar_open_after(self._market, trade.symbol, trade.signal_at)
            if nxt is not None:
                open_px, bar_ts = nxt
                trade.honest_entry = _bps_slip(open_px, trade.direction, entry=True)
                trade.honest_entry_at = bar_ts
                trade.honest_bar_ts = bar_ts
                trade.status = "open"
                trade.notes += f" Honest fill @ {trade.honest_entry:.6g} bar {bar_ts.isoformat()}."
                notes.append(f"honest_fill:{trade.symbol}")

        # Optimistic exit management (always live once opened)
        if trade.optimistic_exit is None:
            reason = should_close(
                direction=trade.direction,
                entry=trade.optimistic_entry,
                mark=mark,
                opened_at=trade.optimistic_entry_at,
                now=now,
            )
            if reason:
                exit_px = _bps_slip(mark, trade.direction, entry=False)
                pnl, ret = unrealized_pnl(
                    direction=trade.direction,
                    entry=trade.optimistic_entry,
                    mark=exit_px,
                    size_usd=trade.size_usd,
                )
                trade.optimistic_exit = exit_px
                trade.optimistic_pnl_usd = pnl
                trade.optimistic_return_pct = ret
                notes.append(f"opt_close:{trade.symbol}:{reason}")

        # Honest exit only after honest fill
        if trade.honest_entry is not None and trade.honest_exit is None:
            reason = should_close(
                direction=trade.direction,
                entry=trade.honest_entry,
                mark=mark,
                opened_at=trade.honest_entry_at or trade.signal_at,
                now=now,
            )
            if reason:
                exit_px = _bps_slip(mark, trade.direction, entry=False)
                pnl, ret = unrealized_pnl(
                    direction=trade.direction,
                    entry=trade.honest_entry,
                    mark=exit_px,
                    size_usd=trade.size_usd,
                )
                trade.honest_exit = exit_px
                trade.honest_pnl_usd = pnl
                trade.honest_return_pct = ret
                trade.close_reason = reason
                notes.append(f"honest_close:{trade.symbol}:{reason}")

        # Fully closed when optimistic resolved; prefer wait for honest if pending briefly
        if trade.optimistic_exit is not None and (
            trade.honest_exit is not None or trade.honest_entry is None
        ):
            # If honest never filled after max hold from signal, close pending as cancel
            if trade.honest_entry is None:
                trade.close_reason = trade.close_reason or "optimistic_done_honest_unfilled"
            trade.status = "closed"
            trade.closed_at = now

        # Or both legs exited
        if trade.optimistic_exit is not None and trade.honest_exit is not None:
            trade.status = "closed"
            trade.closed_at = now

        self._store.upsert(trade)

    def summary(self, *, tick_notes: list[str] | None = None) -> PaperAgentSummary:
        trades = self._store.list_all()
        open_trades = [t for t in trades if t.status in {"pending_honest", "open"}]
        closed = [t for t in trades if t.status == "closed"]
        closed_sorted = sorted(
            closed,
            key=lambda t: t.closed_at or t.signal_at,
            reverse=True,
        )[:20]

        return PaperAgentSummary(
            agent_name=AGENT_NAME,
            starting_cash=self._starting_cash,
            as_of=datetime.now(UTC),
            last_tick_at=self._last_tick_at,
            optimistic=self._ledger("optimistic", trades),
            honest=self._ledger("honest", trades),
            open_trades=sorted(open_trades, key=lambda t: t.signal_at, reverse=True),
            recent_closed=closed_sorted,
            tick_notes=list(tick_notes or []),
        )

    def _ledger(self, mode: str, trades: list[PaperTrade]) -> PaperLedgerSnapshot:
        realized = 0.0
        unrealized = 0.0
        open_n = 0
        closed_n = 0
        wins = 0
        losses = 0

        for t in trades:
            if mode == "optimistic":
                entry = t.optimistic_entry
                exit_px = t.optimistic_exit
                pnl_closed = t.optimistic_pnl_usd
            else:
                entry = t.honest_entry
                exit_px = t.honest_exit
                pnl_closed = t.honest_pnl_usd
                if entry is None:
                    continue

            if exit_px is not None and pnl_closed is not None:
                closed_n += 1
                realized += pnl_closed
                if pnl_closed > 0:
                    wins += 1
                elif pnl_closed < 0:
                    losses += 1
            elif t.status in {"pending_honest", "open"} and t.mark_price is not None:
                open_n += 1
                u_pnl, _ = unrealized_pnl(
                    direction=t.direction,
                    entry=entry,
                    mark=t.mark_price,
                    size_usd=t.size_usd,
                )
                unrealized += u_pnl

        total = realized + unrealized
        equity = self._starting_cash + total
        ret = (total / self._starting_cash) * 100.0 if self._starting_cash else 0.0
        return PaperLedgerSnapshot(
            label=mode,
            starting_cash=self._starting_cash,
            equity=equity,
            realized_pnl=realized,
            unrealized_pnl=unrealized,
            total_pnl=total,
            return_pct=ret,
            open_positions=open_n,
            closed_trades=closed_n,
            wins=wins,
            losses=losses,
        )
