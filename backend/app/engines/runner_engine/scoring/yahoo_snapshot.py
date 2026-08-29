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
    eps_surprise_pct: float | None = None
    eps_surprise_date: date | None = None
    eps_beat_streak: int = 0


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


def quarterly_revenue_series_from_frame(
    frame: object,
) -> tuple[tuple[date, float], ...]:
    """Period-end date + Total Revenue, newest first. Empty when the row is missing."""
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
    pairs: list[tuple[date, float]] = []
    columns = list(getattr(frame, "columns", []))
    values = list(row.tolist()) if hasattr(row, "tolist") else list(row)
    for col, raw in zip(columns, values, strict=False):
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        period_end = _as_date(col)
        if period_end is None:
            continue
        pairs.append((period_end, number))
    if not pairs:
        return ()
    pairs.sort(key=lambda item: item[0], reverse=True)
    return tuple(pairs[:8])


def quarterly_revenues_from_frame(frame: object) -> tuple[float, ...]:
    """Newest-first Total Revenue column from a Yahoo quarterly statement."""
    return tuple(value for _period, value in quarterly_revenue_series_from_frame(frame))


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


def _as_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "date") and callable(value.date):
        try:
            parsed = value.date()
        except Exception:
            parsed = None
        if isinstance(parsed, date):
            return parsed
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _row_float(row: object, *names: str) -> float | None:
    mapping: dict[str, object] = {}
    if hasattr(row, "index"):
        try:
            for key, raw in zip(list(row.index), list(row.tolist()), strict=False):
                mapping[
                    str(key)
                    .lower()
                    .replace("%", "pct")
                    .replace(" ", "")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("_", "")
                ] = raw
        except Exception:
            mapping = {}
    for name in names:
        raw = mapping.get(name)
        if raw is None:
            continue
        try:
            number = float(raw)
        except (TypeError, ValueError):
            continue
        if number != number:
            continue
        return number
    return None


def eps_surprise_from_frame(
    frame: object, *, today: date | None = None
) -> tuple[date | None, float | None, int]:
    """Newest reported EPS surprise. Surprise is Yahoo percent (12.5 = +12.5%)."""
    now = today or datetime.now(UTC).date()
    if frame is None or not hasattr(frame, "iterrows"):
        return None, None, 0
    try:
        if getattr(frame, "empty", False):
            return None, None, 0
    except Exception:
        return None, None, 0

    last_date: date | None = None
    last_surprise: float | None = None
    streak = 0
    streak_alive = True
    try:
        rows = list(frame.iterrows())
    except Exception:
        return None, None, 0

    dated: list[tuple[date, object]] = []
    for index, row in rows:
        when = _as_date(index)
        if when is None or when > now:
            continue
        dated.append((when, row))
    dated.sort(key=lambda item: item[0], reverse=True)

    for when, row in dated:
        reported = _row_float(row, "reportedeps", "actual", "epsactual")
        estimate = _row_float(row, "epsestimate", "estimate")
        surprise = _row_float(row, "surprisepct", "surprise")
        if reported is None:
            continue
        if surprise is None and estimate is not None and abs(estimate) > 1e-9:
            surprise = (reported - estimate) / abs(estimate) * 100.0
        if surprise is None:
            continue
        if last_surprise is None:
            last_date = when
            last_surprise = surprise
        if streak_alive:
            if surprise >= 0:
                streak += 1
            else:
                streak_alive = False
    return last_date, last_surprise, streak


def _earnings_surprise(ticker: object) -> tuple[date | None, float | None, int]:
    for attr in ("earnings_dates", "get_earnings_dates"):
        try:
            raw = getattr(ticker, attr)
            frame = raw() if callable(raw) else raw
        except Exception:
            continue
        when, surprise, streak = eps_surprise_from_frame(frame)
        if surprise is not None:
            return when, surprise, streak
    return None, None, 0


def _parse_info(
    symbol: str,
    info: dict,
    calendar: object | None,
    quarterly_revenue: tuple[float, ...] = (),
    eps_surprise_pct: float | None = None,
    eps_surprise_date: date | None = None,
    eps_beat_streak: int = 0,
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
        eps_surprise_pct=eps_surprise_pct,
        eps_surprise_date=eps_surprise_date,
        eps_beat_streak=eps_beat_streak,
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
            surprise_date, surprise_pct, beat_streak = None, None, 0
            try:
                surprise_date, surprise_pct, beat_streak = _earnings_surprise(ticker)
            except Exception:
                surprise_date, surprise_pct, beat_streak = None, None, 0
            snap = _parse_info(
                normalized,
                info,
                calendar,
                quarterly,
                surprise_pct,
                surprise_date,
                beat_streak,
            )
    except Exception:
        logger.warning("Yahoo runner snapshot failed for %s", normalized, exc_info=True)
        snap = empty_yahoo_snapshot(normalized)

    _SNAPSHOT_CACHE.set(normalized, snap)
    return snap
