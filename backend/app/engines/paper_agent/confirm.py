"""Pre-open confirmation: grade, Fear & Greed (crypto), earnings, and risk/R:R."""

from __future__ import annotations

import logging
from typing import Protocol

from app.engines.event_engine.engine import _fetch_earnings_event
from app.engines.paper_agent.broker import STOP_LOSS_PCT, TAKE_PROFIT_PCT
from app.engines.paper_agent.types import PaperDirection
from app.engines.sentiment_engine.engine import fetch_fear_greed
from app.indicators.atr import calculate_atr
from app.market_data.symbols import (
    FUTURES_BY_SYMBOL,
    AssetClass,
    get_asset_class,
    is_crypto,
    looks_like_us_equity_ticker,
    looks_like_yahoo_future,
)

logger = logging.getLogger(__name__)

MIN_GRADE = "B"
_GRADE_RANK = {"F": 0, "D": 1, "C": 2, "B": 3, "A": 4, "A+": 5}
# Match DecisionPipelineService veto
RISK_VETO_THRESHOLD = 48.0
RISK_VETO_MIN_RR = 1.35
# Extreme F&G: crowd already one-sided (crypto only)
FNG_BLOCK_LONG_ABOVE = 75
FNG_BLOCK_SHORT_BELOW = 20
EARNINGS_VETO_DAYS = 2.0


class _DecisionLike(Protocol):
    def evaluate(self, symbol: str, timeframe: str = "1h"): ...


def grade_meets_floor(grade: str, floor: str = MIN_GRADE) -> bool:
    return _GRADE_RANK.get(grade, -1) >= _GRADE_RANK.get(floor, 99)


def _is_cme_paper(symbol: str, source: str | None = None) -> bool:
    """Yahoo continuous futures — not spot crypto, not a US equity ticker."""
    if source == "cme_futures":
        return True
    normalized = symbol.upper().strip()
    if normalized in FUTURES_BY_SYMBOL:
        return True
    try:
        return get_asset_class(normalized) == AssetClass.FUTURES
    except ValueError:
        return looks_like_yahoo_future(normalized)


def _is_crypto_symbol(symbol: str) -> bool:
    if looks_like_yahoo_future(symbol):
        return False
    try:
        return is_crypto(symbol)
    except ValueError:
        return False


def _is_equity_like(symbol: str) -> bool:
    if looks_like_yahoo_future(symbol):
        return False
    try:
        return get_asset_class(symbol) in {AssetClass.STOCK, AssetClass.ETF}
    except ValueError:
        return looks_like_us_equity_ticker(symbol)


def earnings_soon(symbol: str, *, within_days: float = EARNINGS_VETO_DAYS) -> bool:
    """True when Yahoo calendar shows earnings within ``within_days``. Fail-open."""
    if not _is_equity_like(symbol):
        return False
    try:
        events = _fetch_earnings_event(symbol, horizon_days=max(1, int(within_days) + 1))
    except Exception:
        logger.exception("Paper earnings calendar failed for %s", symbol)
        return False
    return any(days <= within_days for _label, days in events)


def confirm_open(
    *,
    symbol: str,
    direction: PaperDirection,
    pipeline: _DecisionLike | None,
    entry_price: float,
    source: str | None = None,
    market=None,
) -> tuple[str | None, float, float, str]:
    """Return (skip_reason, take_profit_pct, stop_loss_pct, note).

    skip_reason is None when the idea may open. Percent exits come from
    RiskEngine ATR levels (same R:R for long and short). Fallback 6/3 only
    if confirmation is disabled (no pipeline — tests).

    CME Yahoo names skip F&G and the 13-category pipeline; exits come from
    Yahoo OHLCV ATR instead. Squeeze expansion skips F&G/grade the same way.
    """
    if _is_cme_paper(symbol, source):
        return _confirm_cme_open(symbol=symbol, entry_price=entry_price, market=market)

    if source == "squeeze_expansion":
        return _confirm_expansion_open(symbol=symbol, entry_price=entry_price, market=market)

    if pipeline is None:
        return None, TAKE_PROFIT_PCT, STOP_LOSS_PCT, "confirm:off"

    fng = fetch_fear_greed()
    fng_note = ""
    if _is_crypto_symbol(symbol):
        if fng is None:
            return "skip:fng_unavailable", TAKE_PROFIT_PCT, STOP_LOSS_PCT, ""
        fng_value, fng_class = fng
        if direction == "long" and fng_value > FNG_BLOCK_LONG_ABOVE:
            return (
                "skip:fng_greed",
                TAKE_PROFIT_PCT,
                STOP_LOSS_PCT,
                f"F&G {fng_value} ({fng_class})",
            )
        if direction == "short" and fng_value < FNG_BLOCK_SHORT_BELOW:
            return (
                "skip:fng_fear",
                TAKE_PROFIT_PCT,
                STOP_LOSS_PCT,
                f"F&G {fng_value} ({fng_class})",
            )
        fng_note = f"F&G {fng_value} ({fng_class})"
    elif fng is not None:
        fng_note = f"F&G {fng[0]} ({fng[1]})"

    if earnings_soon(symbol):
        return "skip:earnings_soon", TAKE_PROFIT_PCT, STOP_LOSS_PCT, "earnings <=2d"

    try:
        decision = pipeline.evaluate(symbol)
    except Exception:
        logger.exception("Paper confirm evaluate failed for %s", symbol)
        return "skip:decision_error", TAKE_PROFIT_PCT, STOP_LOSS_PCT, ""

    grade = decision.opportunity.trade_grade
    if not grade_meets_floor(grade):
        return (
            f"skip:grade:{grade}",
            TAKE_PROFIT_PCT,
            STOP_LOSS_PCT,
            f"grade {grade} < {MIN_GRADE}",
        )

    risk = decision.risk
    if risk is None:
        return "skip:risk_unavailable", TAKE_PROFIT_PCT, STOP_LOSS_PCT, ""
    if risk.score < RISK_VETO_THRESHOLD or risk.risk_reward_ratio < RISK_VETO_MIN_RR:
        return (
            "skip:risk",
            TAKE_PROFIT_PCT,
            STOP_LOSS_PCT,
            f"risk {risk.score:.0f} R:R {risk.risk_reward_ratio:.2f}",
        )

    sl_pct, tp_pct = _atr_exit_pcts(entry_price, risk.stop_loss, risk.take_profit)
    bits = [f"Confirm grade {grade}"]
    if fng_note:
        bits.append(fng_note)
    bits.append(f"risk {risk.score:.0f}, R:R {risk.risk_reward_ratio:.2f}")
    bits.append(f"ATR SL {sl_pct:.1f}% / TP {tp_pct:.1f}%")
    return None, tp_pct, sl_pct, ", ".join(bits)


def _atr_exit_pcts(entry: float, stop_loss: float, take_profit: float) -> tuple[float, float]:
    """Percent distance from mark to RiskEngine stop / target (direction-agnostic)."""
    if entry <= 0:
        return STOP_LOSS_PCT, TAKE_PROFIT_PCT
    sl = abs(entry - stop_loss) / entry * 100.0
    tp = abs(take_profit - entry) / entry * 100.0
    if sl < 0.4 or tp < sl:
        return STOP_LOSS_PCT, TAKE_PROFIT_PCT
    return sl, tp


def _confirm_expansion_open(
    *,
    symbol: str,
    entry_price: float,
    market=None,
) -> tuple[str | None, float, float, str]:
    """Squeeze trigger path: ATR exits, no F&G, no 13-category grade.

    Crowded-funding / greed vetoes stay on perp_momentum. Expansion is a
    different setup class — confirm the break with ATR, not mean-reversion.
    """
    tp_pct, sl_pct, atr_note = _cme_atr_exit_pcts(market, symbol, entry_price)
    note = atr_note.replace("confirm:cme", "confirm:expansion", 1)
    return None, tp_pct, sl_pct, note


def _confirm_cme_open(
    *,
    symbol: str,
    entry_price: float,
    market=None,
) -> tuple[str | None, float, float, str]:
    """Scanner-gated CME path: Yahoo ATR percents, no F&G, no DecisionPipeline."""
    tp_pct, sl_pct, atr_note = _cme_atr_exit_pcts(market, symbol, entry_price)
    return None, tp_pct, sl_pct, atr_note


def _cme_atr_exit_pcts(market, symbol: str, entry: float) -> tuple[float, float, str]:
    """2 ATR stop / 2–3.5 ATR target from Yahoo 1h bars. Fallback 6/3."""
    fallback_note = "confirm:cme fallback 6/3"
    if market is None or entry <= 0:
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    try:
        df = market.safe_get_ohlcv(symbol, "1h", limit=32)
    except Exception:
        logger.exception("CME ATR OHLCV failed for %s", symbol)
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    if df is None or len(df) < 15:
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    try:
        atr = float(calculate_atr(df["high"], df["low"], df["close"]).iloc[-1])
    except Exception:
        logger.exception("CME ATR calc failed for %s", symbol)
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    if atr <= 0 or entry <= 0:
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    atr_pct = (atr / entry) * 100.0
    stop_mult = 2.0
    if atr_pct >= 4.0:
        tp_mult = 2.0
    elif atr_pct >= 2.5:
        tp_mult = 2.5
    else:
        tp_mult = 3.5
    sl = stop_mult * atr_pct
    tp = tp_mult * atr_pct
    if sl < 0.4 or tp < sl:
        return TAKE_PROFIT_PCT, STOP_LOSS_PCT, fallback_note
    return tp, sl, f"confirm:cme ATR SL {sl:.1f}% / TP {tp:.1f}%"
