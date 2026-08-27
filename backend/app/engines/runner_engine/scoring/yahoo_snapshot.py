"""One Yahoo fetch per symbol for Radar fundamentals / ownership / SI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

import yfinance as yf

from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_SNAPSHOT_CACHE: TTLCache[YahooRunnerSnapshot] = TTLCache(ttl_seconds=1_800.0)


@dataclass(frozen=True)
class YahooRunnerSnapshot:
    """Free Yahoo fields used by Radar dimensions. None = field not present."""

    symbol: str
    fetched_ok: bool
    market_cap: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    earnings_quarterly_growth: float | None = None
    profit_margins: float | None = None
    operating_margins: float | None = None
    return_on_equity: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    short_percent_of_float: float | None = None
    short_ratio: float | None = None
    shares_short: float | None = None
    shares_short_prior: float | None = None
    held_percent_institutions: float | None = None
    held_percent_insiders: float | None = None
    float_shares: float | None = None
    shares_outstanding: float | None = None
    number_of_analysts: int | None = None
    sector: str | None = None
    industry: str | None = None
    earnings_date: date | None = None
    price_to_sales: float | None = None
    week52_change: float | None = None
    quarterly_revenue: tuple[float, ...] = ()


def _num(info: dict, *keys: str) -> float | None:
    for key in keys:
        raw = info.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value != value:  # NaN
            continue
        return value
    return None


def _int(info: dict, *keys: str) -> int | None:
    value = _num(info, *keys)
    if value is None:
        return None
    return int(value)


def _text(info: dict, *keys: str) -> str | None:
    for key in keys:
        raw = info.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _earnings_from_info(info: dict) -> date | None:
    ts = _num(info, "earningsTimestampStart", "earningsTimestamp", "earningsTimestampEnd")
    if ts is None or ts <= 0:
        return None
    try:
        return datetime.fromtimestamp(ts, UTC).date()
    except (OverflowError, OSError, ValueError):
        return None


def _earnings_from_calendar(calendar: object) -> date | None:
    if calendar is None:
        return None
    raw = None
    if isinstance(calendar, dict):
        raw = calendar.get("Earnings Date") or calendar.get("Earnings Date High")
        if isinstance(raw, list) and raw:
            raw = raw[0]
    else:
        try:
            frame = calendar
            if hasattr(frame, "empty") and not frame.empty:
                if "Earnings Date" in getattr(frame, "index", []):
                    raw = frame.loc["Earnings Date"].iloc[0]
                elif "Earnings Date" in getattr(frame, "columns", []):
                    raw = frame["Earnings Date"].iloc[0]
        except Exception:
            raw = None
    if raw is None:
        return None
    try:
        stamp = datetime.fromisoformat(str(raw)[:10])
        return stamp.date()
    except ValueError:
        try:
            return datetime.fromtimestamp(float(raw), UTC).date()
        except (TypeError, ValueError, OverflowError, OSError):
            return None


def quarterly_revenues_from_frame(frame: object) -> tuple[float, ...]:
    """Newest-first Total Revenue column from a Yahoo quarterly statement."""
    if frame is None or not hasattr(frame, "index"):
        return ()
    try:
        if getattr(frame, "empty", False):
            return ()
    except Exception:
        return ()
    labels = [str(idx).strip().lower() for idx in frame.index]
    row_idx = None
    for needle in ("total revenue", "operating revenue", "revenue"):
        for i, label in enumerate(labels):
            if label == needle or needle in label:
                row_idx = i
                break
        if row_idx is not None:
            break
    if row_idx is None:
        return ()
    row = frame.iloc[row_idx]
    pairs: list[tuple[str, float]] = []
    columns = list(getattr(frame, "columns", []))
    values = list(row.tolist()) if hasattr(row, "tolist") else list(row)
    for col, raw in zip(columns, values, strict=False):
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        pairs.append((str(col), number))
    if not pairs:
        return ()

    def _col_key(item: tuple[str, float]) -> str:
        return item[0]

    pairs.sort(key=_col_key, reverse=True)
    return tuple(value for _col, value in pairs[:8])


def _quarterly_revenues(ticker: object) -> tuple[float, ...]:
    for attr in ("quarterly_income_stmt", "quarterly_financials"):
        try:
            frame = getattr(ticker, attr)
        except Exception:
            continue
        revenues = quarterly_revenues_from_frame(frame)
        if revenues:
            return revenues
    return ()


def _parse_info(
    symbol: str,
    info: dict,
    calendar: object | None,
    quarterly_revenue: tuple[float, ...] = (),
) -> YahooRunnerSnapshot:
    earnings = _earnings_from_info(info) or _earnings_from_calendar(calendar)
    return YahooRunnerSnapshot(
        symbol=symbol,
        fetched_ok=True,
        market_cap=_num(info, "marketCap"),
        revenue_growth=_num(info, "revenueGrowth"),
        earnings_growth=_num(info, "earningsGrowth"),
        earnings_quarterly_growth=_num(info, "earningsQuarterlyGrowth"),
        profit_margins=_num(info, "profitMargins"),
        operating_margins=_num(info, "operatingMargins"),
        return_on_equity=_num(info, "returnOnEquity"),
        trailing_pe=_num(info, "trailingPE"),
        forward_pe=_num(info, "forwardPE"),
        short_percent_of_float=_num(info, "shortPercentOfFloat"),
        short_ratio=_num(info, "shortRatio"),
        shares_short=_num(info, "sharesShort"),
        shares_short_prior=_num(info, "sharesShortPriorMonth"),
        held_percent_institutions=_num(info, "heldPercentInstitutions"),
        held_percent_insiders=_num(info, "heldPercentInsiders"),
        float_shares=_num(info, "floatShares"),
        shares_outstanding=_num(info, "sharesOutstanding"),
        number_of_analysts=_int(info, "numberOfAnalystOpinions"),
        sector=_text(info, "sector"),
        industry=_text(info, "industry"),
        earnings_date=earnings,
        price_to_sales=_num(info, "priceToSalesTrailing12Months"),
        week52_change=_num(info, "52WeekChange", "fiftyTwoWeekChange"),
        quarterly_revenue=quarterly_revenue,
    )


def empty_yahoo_snapshot(symbol: str) -> YahooRunnerSnapshot:
    """Explicit miss — used by tests and failed fetches."""
    return YahooRunnerSnapshot(symbol=symbol.upper().strip(), fetched_ok=False)


def fetch_yahoo_runner_snapshot(symbol: str) -> YahooRunnerSnapshot:
    """Cached Yahoo `.info` (+ calendar fallback) for one US ticker."""
    normalized = symbol.upper().strip()
    cached = _SNAPSHOT_CACHE.get(normalized)
    if cached is not None:
        return cached

    try:
        ticker = yf.Ticker(normalized)
        raw_info = ticker.info
        info = raw_info if isinstance(raw_info, dict) else {}
        calendar = None
        if not _earnings_from_info(info):
            try:
                calendar = ticker.calendar
            except Exception:
                calendar = None
        if not info:
            snap = empty_yahoo_snapshot(normalized)
        else:
            quarterly: tuple[float, ...] = ()
            try:
                quarterly = _quarterly_revenues(ticker)
            except Exception:
                quarterly = ()
            snap = _parse_info(normalized, info, calendar, quarterly)
    except Exception:
        logger.warning("Yahoo runner snapshot failed for %s", normalized, exc_info=True)
        snap = empty_yahoo_snapshot(normalized)

    _SNAPSHOT_CACHE.set(normalized, snap)
    return snap
