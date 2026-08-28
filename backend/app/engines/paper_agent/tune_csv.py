"""Export paper-bot trades as a tuning CSV (honest ledger when present)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import UTC, datetime

from app.engines.paper_agent.broker import unrealized_pnl
from app.engines.paper_agent.types import PaperTrade

# Original eight columns stay first so existing spreadsheets still parse.
CSV_COLUMNS = (
    "timestamp",
    "asset_symbol",
    "entry_price",
    "exit_price",
    "pnl_percent",
    "strategy_type",
    "market_condition",
    "user_feedback",
    "source",
    "direction",
    "close_reason",
    "hold_hours",
)

_HIGH_VOL_SETUPS = frozenset({"liq_flush", "squeeze_expansion", "breakout_convexity"})


def paper_trades_to_csv(trades: Iterable[PaperTrade]) -> str:
    """Return CSV text. Newest signal first. Honest fill preferred over optimistic."""
    rows = sorted(trades, key=lambda t: t.signal_at, reverse=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for trade in rows:
        writer.writerow(_row(trade))
    return buf.getvalue()


def _row(trade: PaperTrade) -> dict[str, str]:
    entry, exit_px, pnl = _honest_prices(trade)
    return {
        "timestamp": _timestamp(trade),
        "asset_symbol": trade.symbol.upper(),
        "entry_price": _price(entry),
        "exit_price": _price(exit_px),
        "pnl_percent": _pnl_percent(pnl),
        "strategy_type": trade.setup_type or trade.source,
        "market_condition": market_condition(trade),
        "user_feedback": user_feedback(trade.confidence),
        "source": trade.source,
        "direction": trade.direction,
        "close_reason": (trade.close_reason or "").strip(),
        "hold_hours": _hold_hours(trade),
    }


def _honest_prices(trade: PaperTrade) -> tuple[float | None, float | None, float | None]:
    """Prefer the honest (next-bar) ledger; fall back to optimistic."""
    entry = trade.honest_entry if trade.honest_entry is not None else trade.optimistic_entry
    exit_px = trade.honest_exit if trade.honest_exit is not None else trade.optimistic_exit
    pnl = trade.honest_return_pct
    if pnl is None:
        pnl = trade.optimistic_return_pct
    if (
        pnl is None
        and exit_px is None
        and entry is not None
        and trade.mark_price is not None
        and trade.status in {"pending_honest", "open", "closing"}
    ):
        _, pnl = unrealized_pnl(
            direction=trade.direction,
            entry=entry,
            mark=trade.mark_price,
            size_usd=trade.size_usd,
        )
    if pnl is None and entry is not None and exit_px is not None:
        _, pnl = unrealized_pnl(
            direction=trade.direction,
            entry=entry,
            mark=exit_px,
            size_usd=trade.size_usd,
        )
    return entry, exit_px, pnl


def _aware(stamp: datetime) -> datetime:
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC)


def _timestamp(trade: PaperTrade) -> str:
    stamp = trade.honest_entry_at or trade.optimistic_entry_at or trade.signal_at
    return _aware(stamp).strftime("%Y-%m-%d %H:%M")


def _hold_hours(trade: PaperTrade) -> str:
    """Hours from honest (else optimistic) entry to close, or now if still open."""
    start = trade.honest_entry_at or trade.optimistic_entry_at or trade.signal_at
    end = trade.closed_at
    if end is None and trade.status in {"pending_honest", "open", "closing"}:
        end = datetime.now(UTC)
    if start is None or end is None:
        return ""
    hours = (_aware(end) - _aware(start)).total_seconds() / 3600.0
    if hours < 0:
        return ""
    return f"{hours:.1f}"


def _price(value: float | None) -> str:
    if value is None:
        return ""
    if abs(value) >= 1:
        return f"{value:.2f}"
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _pnl_percent(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.1f}%"


def market_condition(trade: PaperTrade) -> str:
    """Compact regime tag: optional F&G + vol + directional bias."""
    blob = " ".join(trade.factors) + " " + (trade.notes or "")
    low = blob.lower()
    setup = (trade.setup_type or "").lower()
    high_vol = setup in _HIGH_VOL_SETUPS or "oi unwinding" in low or "liq" in setup
    vol = "High_Vol" if high_vol else "Trend"
    fng = ""
    if "greed" in low:
        fng = "Greed_"
    elif "fear" in low:
        fng = "Fear_"
    bias = "Bullish" if trade.direction == "long" else "Bearish"
    return f"{fng}{vol}_{bias}"


def user_feedback(confidence: float) -> str:
    """Bot confidence as a stand-in — the ledger has no human tag."""
    return "Confident" if confidence >= 70 else "Hesitant"
