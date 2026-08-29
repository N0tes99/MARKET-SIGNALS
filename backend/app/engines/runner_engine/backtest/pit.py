"""Point-in-time fund/catalyst series for Radar replay.

Live Yahoo ``info`` (cap, PE, ownership, SI, next earnings) is never written
into history. 8-K/6-K use SEC filing dates. Yahoo quarterlies become knowable
on the matching 10-Q/10-K filing date, or period-end + 45 days if none.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from app.engines.runner_engine.backtest.dataset import DatedFundamentals
from app.engines.runner_engine.scoring.edgar import (
    CATALYST_FORMS,
    STATEMENT_FORMS,
    fetch_edgar_filings,
    snapshot_as_of,
)
from app.engines.runner_engine.scoring.yahoo_dims import score_catalyst, score_fundamental
from app.engines.runner_engine.scoring.yahoo_snapshot import (
    YahooRunnerSnapshot,
    empty_yahoo_snapshot,
    quarterly_revenue_series_from_frame,
)
from app.engines.runner_engine.types import DimensionScore

logger = logging.getLogger(__name__)

STATEMENT_LAG_DAYS = 45
STATEMENT_MATCH_DAYS = 90
CATALYST_WINDOW_DAYS = 14
_FETCH_WORKERS = 2

FilingsFetcher = Callable[[str], tuple[tuple[date, str], ...]]
RevenueFetcher = Callable[[str], tuple[tuple[date, float], ...]]


def statement_knowable_date(
    period_end: date,
    statement_filings: Sequence[date],
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
    match_days: int = STATEMENT_MATCH_DAYS,
) -> date:
    """First 10-Q/10-K after period-end, else a conservative lag."""
    horizon = period_end + timedelta(days=match_days)
    matches = [filed for filed in statement_filings if period_end < filed <= horizon]
    if matches:
        return min(matches)
    return period_end + timedelta(days=lag_days)


def revenues_knowable_as_of(
    series: tuple[tuple[date, float], ...],
    as_of: date,
    statement_filings: Sequence[date],
    *,
    lag_days: int = STATEMENT_LAG_DAYS,
) -> tuple[float, ...]:
    """Newest-first revenues that were public by ``as_of``."""
    known: list[tuple[date, float]] = []
    for period_end, revenue in series:
        if statement_knowable_date(period_end, statement_filings, lag_days=lag_days) <= as_of:
            known.append((period_end, revenue))
    known.sort(key=lambda item: item[0], reverse=True)
    return tuple(revenue for _period, revenue in known[:8])


def _score_fundamentals(revenues: tuple[float, ...]) -> DimensionScore:
    snap = YahooRunnerSnapshot(
        symbol="PIT",
        fetched_ok=True,
        quarterly_revenue=revenues,
    )
    return score_fundamental(snap)


def build_dated_series(
    symbol: str,
    *,
    revenue_series: tuple[tuple[date, float], ...],
    filings: tuple[tuple[date, str], ...],
    lag_days: int = STATEMENT_LAG_DAYS,
    catalyst_window_days: int = CATALYST_WINDOW_DAYS,
) -> tuple[DatedFundamentals, ...]:
    """Full-state snapshots at each knowable event. Later bars pick the latest."""
    statement_filings = tuple(filed for filed, form in filings if form in STATEMENT_FORMS)
    events: set[date] = set()
    for period_end, _revenue in revenue_series:
        events.add(statement_knowable_date(period_end, statement_filings, lag_days=lag_days))
    for filed, form in filings:
        if form in CATALYST_FORMS:
            events.add(filed)
            events.add(filed + timedelta(days=catalyst_window_days + 1))
    snapshots: list[DatedFundamentals] = []
    for event in sorted(events):
        revenues = revenues_knowable_as_of(
            revenue_series,
            event,
            statement_filings,
            lag_days=lag_days,
        )
        fund = _score_fundamentals(revenues)
        edgar = snapshot_as_of(
            symbol,
            filings,
            event,
            window_days=catalyst_window_days,
        )
        catalyst = score_catalyst(
            empty_yahoo_snapshot(symbol),
            today=event,
            edgar=edgar,
        )
        snapshots.append(
            DatedFundamentals(
                as_of=event,
                dimensions={"fundamental": fund, "catalyst": catalyst},
            )
        )
    return tuple(snapshots)


def fetch_quarterly_revenue_series(symbol: str) -> tuple[tuple[date, float], ...]:
    """Yahoo quarterly revenues with period-end dates. Does not touch ``.info``."""
    import yfinance as yf

    try:
        ticker = yf.Ticker(symbol.upper())
    except Exception:
        logger.info("dated_fundamentals yahoo ticker failed for %s", symbol)
        return ()
    for attr in ("quarterly_income_stmt", "quarterly_financials"):
        try:
            frame = getattr(ticker, attr)
        except Exception:
            continue
        series = quarterly_revenue_series_from_frame(frame)
        if series:
            return series
    return ()


def load_dated_fundamentals(
    symbols: tuple[str, ...],
    *,
    filings_fetcher: FilingsFetcher | None = None,
    revenue_fetcher: RevenueFetcher | None = None,
) -> dict[str, tuple[DatedFundamentals, ...]]:
    """Fetch EDGAR history + lagged quarterlies for a study split."""
    filings_load = filings_fetcher or fetch_edgar_filings
    revenue_load = revenue_fetcher or fetch_quarterly_revenue_series
    wanted = tuple(dict.fromkeys(s.upper() for s in symbols))
    filings_map: dict[str, tuple[tuple[date, str], ...]] = {}
    revenue_map: dict[str, tuple[tuple[date, float], ...]] = {}
    workers = min(_FETCH_WORKERS, max(1, len(wanted)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        all_futs: dict = {}
        for sym in wanted:
            all_futs[pool.submit(filings_load, sym)] = ("f", sym)
            all_futs[pool.submit(revenue_load, sym)] = ("r", sym)
        for fut in as_completed(all_futs):
            kind, sym = all_futs[fut]
            try:
                result = fut.result()
            except Exception:
                logger.exception("dated_fundamentals fetch failed for %s", sym)
                continue
            if kind == "f":
                filings_map[sym] = result
            else:
                revenue_map[sym] = result

    out: dict[str, tuple[DatedFundamentals, ...]] = {}
    for sym in wanted:
        series = build_dated_series(
            sym,
            revenue_series=revenue_map.get(sym, ()),
            filings=filings_map.get(sym, ()),
        )
        if series:
            out[sym] = series
    return out
