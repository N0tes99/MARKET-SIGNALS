"""Public paper agent — executes WATCH setups on dual paper ledgers."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.engines.learning_engine.engine import LearningEngine
from app.engines.opportunity_engine.equity_options.scanner import EquityOptionsScanner
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.paper_agent.broker import (
    DEFAULT_SIZE_USD,
    _bps_slip,
    last_price,
    next_bar_open_after,
    should_close,
    unrealized_pnl,
)
from app.engines.paper_agent.confirm import confirm_open
from app.engines.paper_agent.maturity import compute_maturity, map_honest_close_outcome
from app.engines.paper_agent.stamps import mint_stamp, paper_discord_payload
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import (
    PaperAgentSummary,
    PaperDirection,
    PaperLedgerSnapshot,
    PaperMaturitySnapshot,
    PaperTrade,
)
from app.market_data.service import MarketDataService

if TYPE_CHECKING:
    from app.services.decision_pipeline import DecisionPipelineService

logger = logging.getLogger(__name__)

AGENT_NAME = "Signal Engine Paper Agent"
STARTING_CASH = 15_000.0
# Match Layer 2/3 WATCH bar — do not spend a daily slot on IGNORE-band 50–54.9.
MIN_CONFIDENCE = 55.0
MAX_NEW_OPENS_PER_DAY = 3
# Idea discovery is heavier than managing opens — don't rescan every tick.
# 90s keeps pace with keep-warm / dashboard polls so good setups aren't missed all day.
_DISCOVER_INTERVAL_SECONDS = 90.0


def _fingerprint(source: str, symbol: str, setup_type: str, direction: str) -> str:
    raw = f"{source}|{symbol.upper()}|{setup_type}|{direction}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _dir(bias: str) -> PaperDirection | None:
    if bias == "long":
        return "long"
    if bias == "short":
        return "short"
    return None


def us_cash_session_open(now: datetime) -> bool:
    """True Mon–Fri in America/New_York. Weekend equity last prints are stale."""
    aware = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    et = aware.astimezone(ZoneInfo("America/New_York"))
    return et.weekday() < 5


class PaperAgent:
    """Living paper bot: WATCH ideas → dual-ledger fills → public PnL."""

    def __init__(
        self,
        *,
        market_data: MarketDataService,
        crypto_scanner: SetupScanner,
        equity_scanner: EquityOptionsScanner,
        store: PaperTradeStore | None = None,
        learning: LearningEngine | None = None,
        pipeline: DecisionPipelineService | None = None,
        alerts=None,
        starting_cash: float = STARTING_CASH,
        size_usd: float = DEFAULT_SIZE_USD,
    ) -> None:
        self._market = market_data
        self._crypto = crypto_scanner
        self._equity = equity_scanner
        self._store = store or PaperTradeStore()
        self._learning = learning
        self._pipeline = pipeline
        self._alerts = alerts
        self._starting_cash = starting_cash
        self._size_usd = size_usd
        self._last_tick_at: datetime | None = None
        self._last_discover_at: datetime | None = None
        raw = None
        get_meta = getattr(self._store, "get_meta", None)
        if callable(get_meta):
            raw = get_meta("last_tick_at")
            raw_d = get_meta("last_discover_at")
            if raw_d:
                try:
                    self._last_discover_at = datetime.fromisoformat(raw_d)
                except ValueError:
                    self._last_discover_at = None
        if raw:
            try:
                self._last_tick_at = datetime.fromisoformat(raw)
            except ValueError:
                self._last_tick_at = None

    @property
    def store(self) -> PaperTradeStore:
        return self._store

    def reset(self) -> int:
        """Clear all paper trades so both ledgers restart at starting cash."""
        cleared = self._store.clear_all()
        self._last_tick_at = None
        self._last_discover_at = None
        logger.info("Paper agent reset cleared=%d starting_cash=%.0f", cleared, self._starting_cash)
        return cleared

    def _should_discover(self, now: datetime) -> bool:
        if self._last_discover_at is None:
            return True
        return (now - self._last_discover_at).total_seconds() >= _DISCOVER_INTERVAL_SECONDS

    def _opens_on_utc_day(self, now: datetime) -> int:
        day = now.astimezone(UTC).date()
        n = 0
        for t in self._store.list_all():
            sat = t.signal_at
            if sat.tzinfo is None:
                sat = sat.replace(tzinfo=UTC)
            if sat.astimezone(UTC).date() == day:
                n += 1
        return n

    def tick(self) -> list[str]:
        """Advance the agent once: open new ideas, resolve honest fills, manage exits."""
        notes: list[str] = []
        now = datetime.now(UTC)
        active = self._store.fingerprints_active()
        max_open = max(1, int(self._starting_cash // self._size_usd))
        hit_cap = False
        daily_cap_hit = False

        def _slots_left() -> int:
            return max(0, max_open - len(self._store.open_or_pending()))

        discover = self._should_discover(now)
        if discover:
            candidates: list[dict] = []

            # --- Crypto Layer 2 ---
            try:
                crypto_ideas = self._crypto.scan_feed(
                    watch_only=False, min_confidence=MIN_CONFIDENCE
                )
            except Exception:
                logger.exception("Paper agent crypto feed failed")
                crypto_ideas = []
                notes.append("crypto_feed_error")

            for idea in crypto_ideas:
                direction = _dir(idea.direction_bias)
                if direction is None:
                    continue
                if float(idea.confidence) < MIN_CONFIDENCE:
                    continue
                fp = _fingerprint("crypto_setup", idea.symbol, idea.setup_type, direction)
                if fp in active:
                    continue
                candidates.append(
                    {
                        "source": "crypto_setup",
                        "symbol": idea.symbol,
                        "setup_type": idea.setup_type,
                        "direction": direction,
                        "fingerprint": fp,
                        "confidence": float(idea.confidence),
                        "opportunity_score": float(idea.confidence),
                        "factors": list(idea.factors[:5]),
                        "score": float(idea.confidence),
                    }
                )

            # --- Equity Layer 3 ---
            if not us_cash_session_open(now):
                notes.append("skip:equity_weekend")
                equity_ideas = []
            else:
                try:
                    equity_ideas = self._equity.scan_feed(
                        watch_only=False,
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
                if float(idea.confidence) < MIN_CONFIDENCE:
                    continue
                fp = _fingerprint("equity_setup", idea.symbol, idea.setup_type, direction)
                if fp in active:
                    continue
                score = float(getattr(idea, "opportunity_score", idea.confidence))
                candidates.append(
                    {
                        "source": "equity_setup",
                        "symbol": idea.symbol,
                        "setup_type": idea.setup_type,
                        "direction": direction,
                        "fingerprint": fp,
                        "confidence": float(idea.confidence),
                        "opportunity_score": score,
                        "factors": list(idea.factors[:5]),
                        "score": score,
                    }
                )

            candidates.sort(key=lambda c: c["score"], reverse=True)
            opens_today = self._opens_on_utc_day(now)
            daily_left = max(0, MAX_NEW_OPENS_PER_DAY - opens_today)
            if daily_left <= 0 and candidates:
                daily_cap_hit = True
                notes.append(f"skip:daily_cap:{MAX_NEW_OPENS_PER_DAY}")

            for cand in candidates:
                if daily_left <= 0:
                    daily_cap_hit = True
                    break
                if _slots_left() <= 0:
                    hit_cap = True
                    break
                skip, tp_pct, sl_pct, confirm_note = self._confirm_open(
                    cand["symbol"], cand["direction"]
                )
                if skip:
                    notes.append(f"{skip}:{cand['symbol']}")
                    logger.info(
                        "paper_skip confirm %s %s %s",
                        cand["symbol"],
                        cand["setup_type"],
                        skip,
                    )
                    continue
                trade = self._open_from_signal(
                    source=cand["source"],
                    symbol=cand["symbol"],
                    setup_type=cand["setup_type"],
                    direction=cand["direction"],
                    fingerprint=cand["fingerprint"],
                    confidence=cand["confidence"],
                    opportunity_score=cand["opportunity_score"],
                    factors=cand["factors"],
                    now=now,
                    take_profit_pct=tp_pct,
                    stop_loss_pct=sl_pct,
                    confirm_note=confirm_note,
                )
                if trade:
                    notes.append(f"open:{trade.symbol}:{trade.setup_type}:{trade.size_usd:.0f}")
                    active.add(cand["fingerprint"])
                    daily_left -= 1
                    logger.info(
                        "paper_open id=%s symbol=%s setup=%s conf=%.1f score=%.1f daily_left=%d",
                        trade.id,
                        trade.symbol,
                        trade.setup_type,
                        trade.confidence,
                        trade.opportunity_score,
                        daily_left,
                    )

            if daily_cap_hit and f"skip:daily_cap:{MAX_NEW_OPENS_PER_DAY}" not in notes:
                notes.append(f"skip:daily_cap:{MAX_NEW_OPENS_PER_DAY}")

            self._last_discover_at = now
            set_meta = getattr(self._store, "set_meta", None)
            if callable(set_meta):
                set_meta("last_discover_at", now.isoformat())
        else:
            notes.append("discover:skipped")

        if hit_cap:
            notes.append(f"skip:max_open:{max_open}")

        # --- Manage open / pending / closing ---
        for trade in list(self._store.open_or_pending()):
            self._advance_trade(trade, now=now, notes=notes)

        self._last_tick_at = now
        set_meta = getattr(self._store, "set_meta", None)
        if callable(set_meta):
            set_meta("last_tick_at", now.isoformat())
        return notes

    def _confirm_open(
        self, symbol: str, direction: PaperDirection
    ) -> tuple[str | None, float, float, str]:
        px = last_price(self._market, symbol) or 0.0
        return confirm_open(
            symbol=symbol,
            direction=direction,
            pipeline=self._pipeline,
            entry_price=px,
        )

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
        take_profit_pct: float = 6.0,
        stop_loss_pct: float = 3.0,
        confirm_note: str = "",
    ) -> PaperTrade | None:
        px = last_price(self._market, symbol)
        if px is None or px <= 0:
            logger.info("Paper skip %s — no mark", symbol)
            return None

        opt_entry = _bps_slip(px, direction, entry=True)
        size = float(self._size_usd)
        if size <= 0:
            logger.warning("Paper skip %s — invalid size_usd=%s", symbol, size)
            return None

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
            size_usd=size,
            status="pending_honest",
            optimistic_entry=opt_entry,
            optimistic_entry_at=now,
            mark_price=px,
            factors=factors,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            notes=(
                f"Notional ${size:,.0f}. Optimistic fill @ {opt_entry:.6g} "
                f"(signal last {px:.6g} + slip). Honest fill awaits next 15m bar open. "
                f"Exits ATR SL {stop_loss_pct:.1f}% / TP {take_profit_pct:.1f}%. "
                f"{confirm_note}".strip()
            ),
        )
        stamp = mint_stamp(trade.id)
        trade.stamp = stamp.line

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
        self._remember_open(trade)
        self._ping_discord("open", trade)
        logger.info(
            "Paper open %s %s %s conf=%.1f opt=%.6g honest=%s stamp=%s",
            trade.symbol,
            trade.setup_type,
            trade.direction,
            trade.confidence,
            trade.optimistic_entry,
            f"{trade.honest_entry:.6g}" if trade.honest_entry else "pending",
            stamp.serial,
        )
        return trade

    def _ping_discord(self, kind: str, trade: PaperTrade) -> None:
        if self._alerts is None:
            return
        try:
            configured = getattr(self._alerts, "discord_configured", None)
            if callable(configured) and not configured():
                return
            stamp = mint_stamp(trade.id)
            content, embed, png = paper_discord_payload(kind, trade, stamp)
            sender = getattr(self._alerts, "send_embed", None)
            if not callable(sender):
                return
            ok = sender(
                trade.symbol,
                embed,
                content=content,
                username="Paper Desk",
                files=[("paper-stamp.png", png)],
            )
            if ok:
                logger.info(
                    "paper_discord %s %s %s", kind, trade.symbol, stamp.serial
                )
        except Exception:
            logger.exception("paper_discord failed %s %s", kind, trade.symbol)

    def _remember_open(self, trade: PaperTrade) -> None:
        if self._learning is None or trade.signal_record_id:
            return
        try:
            record = self._learning.record_paper_open(
                paper_trade_id=trade.id,
                symbol=trade.symbol,
                setup_type=trade.setup_type,
                direction=trade.direction,
                confidence=trade.confidence,
                opportunity_score=trade.opportunity_score,
                entry_price=trade.optimistic_entry,
                factors=trade.factors,
            )
            trade.signal_record_id = str(record.id)
            self._store.upsert(trade)
            logger.info(
                "paper_memory_open trade=%s record=%s symbol=%s",
                trade.id,
                record.id,
                trade.symbol,
            )
        except Exception:
            logger.exception("Paper memory open failed trade=%s", trade.id)

    def _remember_close(self, trade: PaperTrade) -> None:
        if self._learning is None:
            return
        try:
            outcome, ret = map_honest_close_outcome(trade)
            resolved = self._learning.resolve_paper_close(
                paper_trade_id=trade.id,
                outcome=outcome,
                realized_return_pct=ret,
                close_reason=trade.close_reason,
            )
            if resolved is None and trade.signal_record_id is None:
                # Close arrived without open memory (legacy) — create then resolve.
                self._remember_open(trade)
                resolved = self._learning.resolve_paper_close(
                    paper_trade_id=trade.id,
                    outcome=outcome,
                    realized_return_pct=ret,
                    close_reason=trade.close_reason,
                )
            if resolved is not None:
                logger.info(
                    "paper_memory_close trade=%s record=%s outcome=%s ret=%s",
                    trade.id,
                    resolved.id,
                    outcome,
                    f"{ret:.3f}" if ret is not None else "-",
                )
        except Exception:
            logger.exception("Paper memory close failed trade=%s", trade.id)

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
                take_profit_pct=trade.take_profit_pct,
                stop_loss_pct=trade.stop_loss_pct,
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
                trade.close_reason = trade.close_reason or reason
                notes.append(f"opt_close:{trade.symbol}:{reason}")
                logger.info(
                    "paper_opt_close id=%s symbol=%s reason=%s pnl=%.2f exit=%.6g",
                    trade.id,
                    trade.symbol,
                    reason,
                    pnl,
                    exit_px,
                )

        # Honest exit only after honest fill
        if trade.honest_entry is not None and trade.honest_exit is None:
            reason = should_close(
                direction=trade.direction,
                entry=trade.honest_entry,
                mark=mark,
                opened_at=trade.honest_entry_at or trade.signal_at,
                now=now,
                take_profit_pct=trade.take_profit_pct,
                stop_loss_pct=trade.stop_loss_pct,
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
                logger.info(
                    "paper_honest_close id=%s symbol=%s reason=%s pnl=%.2f exit=%.6g",
                    trade.id,
                    trade.symbol,
                    reason,
                    pnl,
                    exit_px,
                )

        prev = trade.status
        # Opt done + honest never filled → fully closed
        if trade.optimistic_exit is not None and trade.honest_entry is None:
            trade.close_reason = trade.close_reason or "optimistic_done_honest_unfilled"
            trade.status = "closed"
            trade.closed_at = trade.closed_at or now
        # Both legs exited → fully closed
        elif trade.optimistic_exit is not None and trade.honest_exit is not None:
            trade.status = "closed"
            trade.closed_at = trade.closed_at or now
        # Opt done, honest still live → show in history while managing honest
        elif (
            trade.optimistic_exit is not None
            and trade.honest_entry is not None
            and trade.honest_exit is None
        ):
            trade.status = "closing"

        if trade.status == "closed" and prev != "closed":
            notes.append(f"paper_close:{trade.symbol}:{trade.close_reason or 'done'}")
            logger.info(
                "paper_close id=%s symbol=%s reason=%s opt_pnl=%s honest_pnl=%s",
                trade.id,
                trade.symbol,
                trade.close_reason or "done",
                f"{trade.optimistic_pnl_usd:.2f}" if trade.optimistic_pnl_usd is not None else "-",
                f"{trade.honest_pnl_usd:.2f}" if trade.honest_pnl_usd is not None else "-",
            )
            self._remember_close(trade)
            self._ping_discord("close", trade)
        elif trade.status == "closing" and prev != "closing":
            notes.append(f"paper_closing:{trade.symbol}:{trade.close_reason or 'opt_done'}")
            logger.info(
                "paper_closing id=%s symbol=%s reason=%s opt_pnl=%.2f honest=open",
                trade.id,
                trade.symbol,
                trade.close_reason or "opt_done",
                trade.optimistic_pnl_usd or 0.0,
            )

        self._store.upsert(trade)

    def maturity(self) -> PaperMaturitySnapshot:
        """Training readiness from honest closes + paper learning memory."""
        memory: list = []
        if self._learning is not None:
            try:
                memory = self._learning.list_paper_memory(limit=500)
            except Exception:
                logger.exception("Paper maturity memory load failed")
                memory = []
        raw = compute_maturity(
            self._store.list_all(),
            starting_cash=self._starting_cash,
            memory_records=memory,
        )
        return PaperMaturitySnapshot(
            honest_closed=raw.honest_closed,
            memory_outcomes=raw.memory_outcomes,
            win_rate=raw.win_rate,
            avg_return_pct=raw.avg_return_pct,
            expectancy_ok=raw.expectancy_ok,
            max_drawdown_pct=raw.max_drawdown_pct,
            drawdown_ok=raw.drawdown_ok,
            target_honest_closed=raw.target_honest_closed,
            target_memory_outcomes=raw.target_memory_outcomes,
            score_pct=raw.score_pct,
            ready_for_private_live=raw.ready_for_private_live,
            blockers=list(raw.blockers or []),
        )

    def summary(self, *, tick_notes: list[str] | None = None) -> PaperAgentSummary:
        trades = self._store.list_all()
        open_trades = [t for t in trades if t.status in {"pending_honest", "open"}]
        # Include "closing" so optimistic exits appear in history while honest finishes.
        history = [t for t in trades if t.status in {"closing", "closed"}]
        history_sorted = sorted(
            history,
            key=lambda t: t.closed_at or t.signal_at,
            reverse=True,
        )[:20]

        now = datetime.now(UTC)
        return PaperAgentSummary(
            agent_name=AGENT_NAME,
            starting_cash=self._starting_cash,
            as_of=now,
            last_tick_at=self._last_tick_at,
            optimistic=self._ledger("optimistic", trades),
            honest=self._ledger("honest", trades),
            open_trades=sorted(open_trades, key=lambda t: t.signal_at, reverse=True),
            recent_closed=history_sorted,
            tick_notes=list(tick_notes or []),
            maturity=self.maturity(),
            opens_today=self._opens_on_utc_day(now),
            daily_open_cap=MAX_NEW_OPENS_PER_DAY,
        )

    def _ledger(self, mode: str, trades: list[PaperTrade]) -> PaperLedgerSnapshot:
        realized = 0.0
        unrealized = 0.0
        open_n = 0
        closed_n = 0
        wins = 0
        losses = 0
        deployed = 0.0

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

            # Prefer stored closed PnL. If exit exists without PnL (legacy/partial row),
            # derive from entry→exit — never mark-to-market a finished leg (that can flip
            # sign if price recovered after a stop and make a losing book look green).
            if exit_px is not None:
                if pnl_closed is None:
                    pnl_closed, _ = unrealized_pnl(
                        direction=t.direction,
                        entry=entry,
                        mark=exit_px,
                        size_usd=t.size_usd,
                    )
                closed_n += 1
                realized += pnl_closed
                if pnl_closed > 0:
                    wins += 1
                elif pnl_closed < 0:
                    losses += 1
            elif (
                t.status in {"pending_honest", "open", "closing"}
                and t.mark_price is not None
            ):
                open_n += 1
                deployed += t.size_usd
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
            deployed_usd=deployed,
            size_usd=self._size_usd,
        )
