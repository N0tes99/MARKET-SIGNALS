"""Option chain fetch adapter (Yahoo via yfinance) — replaceable later."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class RawOptionRow:
    """Normalized option quote row from any provider."""

    expiry: str
    strike: float
    right: str  # call | put
    bid: float | None
    ask: float | None
    volume: int | None
    open_interest: int | None
    iv: float | None


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        result = float(value)
        if result != result:  # NaN
            return None
        return result
    except (TypeError, ValueError):
        return None


def _safe_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        if value != value:  # NaN
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_yahoo_option_chain(
    symbol: str,
    *,
    max_expiries: int = 4,
    as_of: date | None = None,
) -> list[RawOptionRow]:
    """Fetch near-term option chain rows for a US equity/ETF.

    Soft-fails to [] on network / missing options.
    """
    normalized = symbol.upper()
    today = as_of or datetime.now(UTC).date()
    try:
        ticker = yf.Ticker(normalized)
        expiries = list(ticker.options or [])
    except Exception:
        logger.exception("Option expiry list failed for %s", normalized)
        return []

    if not expiries:
        return []

    scored: list[tuple[int, str]] = []
    for exp in expiries:
        try:
            exp_date = date.fromisoformat(exp)
        except ValueError:
            continue
        dte = (exp_date - today).days
        if dte < 5:
            continue
        preference = abs(dte - 28)
        scored.append((preference, exp))
    scored.sort(key=lambda item: item[0])
    chosen = [exp for _, exp in scored[:max_expiries]]
    if not chosen:
        return []

    rows: list[RawOptionRow] = []
    for exp in chosen:
        try:
            chain = ticker.option_chain(exp)
        except Exception:
            logger.warning("option_chain failed for %s %s", normalized, exp, exc_info=True)
            continue
        for right, frame in (("call", chain.calls), ("put", chain.puts)):
            if frame is None or frame.empty:
                continue
            for _, row in frame.iterrows():
                strike = _safe_float(row.get("strike"))
                if strike is None or strike <= 0:
                    continue
                rows.append(
                    RawOptionRow(
                        expiry=exp,
                        strike=strike,
                        right=right,
                        bid=_safe_float(row.get("bid")),
                        ask=_safe_float(row.get("ask")),
                        volume=_safe_int(row.get("volume")),
                        open_interest=_safe_int(row.get("openInterest")),
                        iv=_safe_float(row.get("impliedVolatility")),
                    )
                )
    return rows
