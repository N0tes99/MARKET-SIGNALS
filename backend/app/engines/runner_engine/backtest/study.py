"""Run a lead-time study on truncated daily paths."""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import pandas as pd

from app.engines.runner_engine.backtest.dataset import (
    STUDY_BENCHMARKS,
    STUDY_SYMBOLS,
    DatedFundamentals,
)
from app.engines.runner_engine.backtest.multiples import (
    MultipleLabels,
    bar_date,
    days_between,
    label_multiples,
    max_drawdown_pct,
)
from app.engines.runner_engine.backtest.replay import (
    ReplayPoint,
    first_list_date,
    lead_days,
    offset_snapshots,
    walk_signals,
)
from app.engines.runner_engine.config import RUNNER_PHASE, RunnerConfig, default_runner_config
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

FrameFetcher = Callable[[str], pd.DataFrame | None]

_CACHE: TTLCache[LeadTimeStudy] = TTLCache(ttl_seconds=1800.0)
_FETCH_WORKERS = 3


@dataclass
class CaseResult:
    """One symbol's path labels + first Radar prints."""

    symbol: str
    bars: int
    error: str | None = None
    trough_date: date | None = None
    trough_close: float | None = None
    hit_2x: bool = False
    hit_5x: bool = False
    hit_10x: bool = False
    date_2x: date | None = None
    date_5x: date | None = None
    date_10x: date | None = None
    days_to_2x: int | None = None
    days_to_5x: int | None = None
    days_to_10x: int | None = None
    first_early: date | None = None
    first_ignition: date | None = None
    first_running: date | None = None
    lead_days_to_2x: int | None = None
    late_for_2x: bool = False
    max_dd_after_early_pct: float | None = None
    snapshots: list[ReplayPoint] = field(default_factory=list)


@dataclass
class StudyMetrics:
    """Precision / recall / FPR / lead time — structure-tape replay."""

    n_cases: int = 0
    n_2x: int = 0
    n_5x: int = 0
    n_10x: int = 0
    n_signaled_early: int = 0
    true_positives_2x: int = 0
    false_positives_2x: int = 0
    false_negatives_2x: int = 0
    precision_2x: float | None = None
    recall_2x: float | None = None
    false_positive_rate_2x: float | None = None
    true_positives_5x: int = 0
    false_positives_5x: int = 0
    false_negatives_5x: int = 0
    precision_5x: float | None = None
    recall_5x: float | None = None
    false_positive_rate_5x: float | None = None
    median_lead_days_2x: float | None = None
    median_days_to_2x: float | None = None
    median_days_to_5x: float | None = None
    median_max_dd_pct: float | None = None


@dataclass
class LeadTimeStudy:
    """Aggregate Phase 5 v0 study."""

    phase: str
    mode: str
    generated_at: datetime
    look_ahead: str
    cases: list[CaseResult]
    metrics: StudyMetrics


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _idx_on_date(df: pd.DataFrame, target: date | None) -> int | None:
    if target is None or df is None or df.empty:
        return None
    for i, ts in enumerate(df["timestamp"]):
        if bar_date(ts) >= target:
            return i
    return None


def replay_case(
    symbol: str,
    ohlcv: pd.DataFrame,
    *,
    bench: pd.DataFrame | None = None,
    config: RunnerConfig | None = None,
    dated_fundamentals: tuple[DatedFundamentals, ...] = (),
    step: int = 5,
) -> CaseResult:
    """Label multiples, walk truncated prefixes, measure lead time."""
    cfg = config or default_runner_config()
    if ohlcv is None or ohlcv.empty:
        return CaseResult(symbol=symbol, bars=0, error="no bars")

    labels: MultipleLabels = label_multiples(ohlcv)
    points = walk_signals(
        ohlcv,
        bench=bench,
        config=cfg,
        dated_fundamentals=dated_fundamentals,
        step=step,
    )
    t0 = labels.hit_date[2] or bar_date(ohlcv["timestamp"].iloc[-1])
    snaps = offset_snapshots(
        ohlcv,
        t0,
        bench=bench,
        config=cfg,
        dated_fundamentals=dated_fundamentals,
    )
    first_early = first_list_date(points, "early")
    first_ignition = first_list_date(points, "ignition")
    first_running = first_list_date(points, "running")
    lead = lead_days(first_early, labels.hit_date[2])
    late = bool(labels.hit_2x and first_early is not None and lead is None)

    early_idx = _idx_on_date(ohlcv, first_early)
    end_idx = labels.hit_idx[2] if labels.hit_idx[2] is not None else len(ohlcv) - 1
    dd = None
    if early_idx is not None:
        dd = max_drawdown_pct(ohlcv, early_idx, end_idx)

    return CaseResult(
        symbol=symbol.upper(),
        bars=len(ohlcv),
        trough_date=labels.trough_date,
        trough_close=round(labels.trough_close, 4) if labels.trough_close else None,
        hit_2x=labels.hit_2x,
        hit_5x=labels.hit_5x,
        hit_10x=labels.hit_10x,
        date_2x=labels.hit_date[2],
        date_5x=labels.hit_date[5],
        date_10x=labels.hit_date[10],
        days_to_2x=days_between(labels.trough_date, labels.hit_date[2]),
        days_to_5x=days_between(labels.trough_date, labels.hit_date[5]),
        days_to_10x=days_between(labels.trough_date, labels.hit_date[10]),
        first_early=first_early,
        first_ignition=first_ignition,
        first_running=first_running,
        lead_days_to_2x=lead,
        late_for_2x=late,
        max_dd_after_early_pct=dd,
        snapshots=snaps,
    )


def aggregate_metrics(cases: list[CaseResult]) -> StudyMetrics:
    usable = [c for c in cases if c.error is None]
    n_2x = sum(1 for c in usable if c.hit_2x)
    n_5x = sum(1 for c in usable if c.hit_5x)
    n_10x = sum(1 for c in usable if c.hit_10x)
    signaled = [c for c in usable if c.first_early is not None]
    tp = sum(1 for c in signaled if c.hit_2x)
    fp = sum(1 for c in signaled if not c.hit_2x)
    fn = sum(1 for c in usable if c.hit_2x and c.first_early is None)
    controls = [c for c in usable if not c.hit_2x]
    precision = (tp / (tp + fp)) if (tp + fp) else None
    recall = (tp / (tp + fn)) if (tp + fn) else None
    fpr = (fp / len(controls)) if controls else None
    tp5 = sum(1 for c in signaled if c.hit_5x)
    fp5 = sum(1 for c in signaled if not c.hit_5x)
    fn5 = sum(1 for c in usable if c.hit_5x and c.first_early is None)
    controls5 = [c for c in usable if not c.hit_5x]
    precision5 = (tp5 / (tp5 + fp5)) if (tp5 + fp5) else None
    recall5 = (tp5 / (tp5 + fn5)) if (tp5 + fn5) else None
    fpr5 = (fp5 / len(controls5)) if controls5 else None
    leads = [float(c.lead_days_to_2x) for c in usable if c.lead_days_to_2x is not None]
    d2 = [float(c.days_to_2x) for c in usable if c.days_to_2x is not None]
    d5 = [float(c.days_to_5x) for c in usable if c.days_to_5x is not None]
    dds = [float(c.max_dd_after_early_pct) for c in usable if c.max_dd_after_early_pct is not None]
    return StudyMetrics(
        n_cases=len(usable),
        n_2x=n_2x,
        n_5x=n_5x,
        n_10x=n_10x,
        n_signaled_early=len(signaled),
        true_positives_2x=tp,
        false_positives_2x=fp,
        false_negatives_2x=fn,
        precision_2x=round(precision, 3) if precision is not None else None,
        recall_2x=round(recall, 3) if recall is not None else None,
        false_positive_rate_2x=round(fpr, 3) if fpr is not None else None,
        true_positives_5x=tp5,
        false_positives_5x=fp5,
        false_negatives_5x=fn5,
        precision_5x=round(precision5, 3) if precision5 is not None else None,
        recall_5x=round(recall5, 3) if recall5 is not None else None,
        false_positive_rate_5x=round(fpr5, 3) if fpr5 is not None else None,
        median_lead_days_2x=_median(leads),
        median_days_to_2x=_median(d2),
        median_days_to_5x=_median(d5),
        median_max_dd_pct=_median(dds),
    )


def run_study(
    frames: dict[str, pd.DataFrame],
    symbols: tuple[str, ...] = STUDY_SYMBOLS,
    *,
    config: RunnerConfig | None = None,
    dated_fundamentals: dict[str, tuple[DatedFundamentals, ...]] | None = None,
    step: int = 5,
    mode: str = "structure_tape",
) -> LeadTimeStudy:
    """Replay each symbol. ``frames`` must already be truncated-capable full paths."""
    cfg = config or default_runner_config()
    bench = frames.get("SMH")
    if bench is None or bench.empty:
        bench = frames.get("SPY")
    cases: list[CaseResult] = []
    for symbol in symbols:
        key = symbol.upper()
        df = frames.get(key)
        if df is None or df.empty:
            cases.append(CaseResult(symbol=key, bars=0, error="missing ohlcv"))
            continue
        try:
            cases.append(
                replay_case(
                    key,
                    df,
                    bench=bench,
                    config=cfg,
                    dated_fundamentals=(dated_fundamentals or {}).get(key, ()),
                    step=step,
                )
            )
        except Exception:
            logger.exception("runner_backtest failed for %s", key)
            cases.append(CaseResult(symbol=key, bars=len(df), error="replay failed"))

    return LeadTimeStudy(
        phase=RUNNER_PHASE,
        mode=mode,
        generated_at=datetime.now(UTC),
        look_ahead=(
            "structure tape truncated at each as-of; current Yahoo fundamentals unused"
        ),
        cases=cases,
        metrics=aggregate_metrics(cases),
    )


def fetch_daily_history(symbol: str, period: str = "5y") -> pd.DataFrame | None:
    """Yahoo daily bars for the study only — not used as live Radar fundamentals."""
    import yfinance as yf

    from app.market_data.normalizer import STANDARD_COLUMNS
    from app.market_data.providers.yahoo import timestamp_to_utc

    try:
        raw = yf.Ticker(symbol.upper()).history(
            period=period,
            interval="1d",
            auto_adjust=True,
        )
    except Exception:
        logger.info("runner_backtest yahoo history failed for %s", symbol)
        return None
    if raw is None or raw.empty:
        return None
    raw = raw.reset_index()
    ts_col = "Datetime" if "Datetime" in raw.columns else "Date"
    rows = [
        {
            "timestamp": timestamp_to_utc(row[ts_col]),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]) if "Volume" in raw.columns else 0.0,
        }
        for _, row in raw.iterrows()
    ]
    return pd.DataFrame(rows, columns=STANDARD_COLUMNS)


def load_study_frames(
    symbols: tuple[str, ...] = STUDY_SYMBOLS,
    *,
    fetcher: FrameFetcher | None = None,
) -> dict[str, pd.DataFrame]:
    """Fetch daily history for study names + RS benches."""
    load = fetcher or fetch_daily_history
    wanted = tuple(dict.fromkeys((*symbols, *STUDY_BENCHMARKS)))
    frames: dict[str, pd.DataFrame] = {}
    workers = min(_FETCH_WORKERS, len(wanted))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(load, sym): sym for sym in wanted}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                df = fut.result()
            except Exception:
                logger.exception("runner_backtest fetch failed for %s", sym)
                continue
            if df is not None and not df.empty:
                frames[sym.upper()] = df
    return frames


def cached_live_study(
    *,
    fetcher: FrameFetcher | None = None,
    symbols: tuple[str, ...] = STUDY_SYMBOLS,
) -> LeadTimeStudy:
    """TTL-cached live Yahoo 5y structure-tape study."""

    def _build() -> LeadTimeStudy:
        frames = load_study_frames(symbols, fetcher=fetcher)
        return run_study(frames, symbols, mode="structure_tape")

    if fetcher is not None:
        return _build()
    return _CACHE.get_or_set("study_v0_with_controls", _build)
