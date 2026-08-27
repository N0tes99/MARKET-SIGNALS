"""OHLCV warehouse — in-memory ring plus Postgres when migrated."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from threading import Lock

import pandas as pd
from sqlalchemy import create_engine, desc, inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.data_lake.schemas import OhlcvBar
from app.engines.learning_engine.postgres_store import to_sync_database_url
from app.models.ohlcv_bar import OhlcvBarModel

logger = logging.getLogger(__name__)

_PERSIST_TIMEFRAMES = frozenset({"5m", "15m", "1h", "4h", "1d"})
_lock = Lock()
_engine = None
_Session = None
_memory: dict[tuple[str, str, datetime], OhlcvBar] = {}


def reset_memory_store() -> None:
    """Drop the in-process warehouse (tests)."""
    with _lock:
        _memory.clear()


def _skip_postgres() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    return settings.signal_store.lower().strip() == "memory"


def _session_factory():
    global _engine, _Session
    if _skip_postgres():
        return None
    with _lock:
        if _Session is not None:
            return _Session
        url = to_sync_database_url(settings.database_url)
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_timeout=3,
            connect_args={"connect_timeout": 2},
        )
        if not inspect(_engine).has_table("ohlcv_bars"):
            logger.warning("ohlcv_bars missing — warehouse stays in-memory")
            return None
        _Session = sessionmaker(bind=_engine, expire_on_commit=False)
        return _Session


def _normalize_ts(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def bars_from_frame(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    source: str = "live",
) -> list[OhlcvBar]:
    """Convert a standard OHLCV frame into warehouse bars."""
    if df is None or df.empty:
        return []
    out: list[OhlcvBar] = []
    for row in df.itertuples(index=False):
        raw_ts = getattr(row, "timestamp", None)
        if raw_ts is None:
            continue
        ts = pd.Timestamp(raw_ts)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        out.append(
            OhlcvBar(
                symbol=symbol.upper(),
                timeframe=timeframe,
                ts=_normalize_ts(ts.to_pydatetime()),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
        )
    return out


def _remember(bars: list[OhlcvBar]) -> None:
    with _lock:
        for bar in bars:
            _memory[(bar.symbol, bar.timeframe, bar.ts)] = bar
        if len(_memory) > 50_000:
            oldest = sorted(_memory, key=lambda k: k[2])[:10_000]
            for key in oldest:
                _memory.pop(key, None)


def upsert_bars(bars: list[OhlcvBar], *, source: str = "live") -> int:
    """Persist bars; always keep an in-memory copy. Returns rows attempted."""
    if not bars:
        return 0
    _remember(bars)
    Session = None
    try:
        Session = _session_factory()
    except Exception:
        logger.debug("ohlcv warehouse session skipped", exc_info=True)
    if Session is None:
        return len(bars)
    now_source = source
    try:
        with Session() as session:
            for bar in bars:
                stmt = pg_insert(OhlcvBarModel).values(
                    symbol=bar.symbol,
                    timeframe=bar.timeframe,
                    ts=bar.ts,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    source=now_source,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["symbol", "timeframe", "ts"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "source": stmt.excluded.source,
                    },
                )
                session.execute(stmt)
            session.commit()
    except Exception:
        logger.debug("ohlcv warehouse upsert failed", exc_info=True)
    return len(bars)


def persist_ohlcv_frame(
    df: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    source: str = "live",
) -> int:
    """Write-through from live fetches. Skips 1m noise."""
    if timeframe not in _PERSIST_TIMEFRAMES:
        return 0
    bars = bars_from_frame(df, symbol=symbol, timeframe=timeframe, source=source)
    return upsert_bars(bars, source=source)


def get_bars(
    symbol: str,
    timeframe: str,
    limit: int = 200,
) -> list[OhlcvBar]:
    """Newest-last bars for a symbol/timeframe."""
    normalized = symbol.upper()
    try:
        Session = _session_factory()
        if Session is not None:
            with Session() as session:
                rows = session.scalars(
                    select(OhlcvBarModel)
                    .where(
                        OhlcvBarModel.symbol == normalized,
                        OhlcvBarModel.timeframe == timeframe,
                    )
                    .order_by(desc(OhlcvBarModel.ts))
                    .limit(limit)
                ).all()
            bars = [
                OhlcvBar(
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    ts=_normalize_ts(row.ts),
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    volume=float(row.volume),
                )
                for row in reversed(rows)
            ]
            if bars:
                return bars
    except Exception:
        logger.debug("ohlcv warehouse read failed", exc_info=True)

    with _lock:
        matching = [
            bar
            for (sym, tf, _ts), bar in _memory.items()
            if sym == normalized and tf == timeframe
        ]
    matching.sort(key=lambda b: b.ts)
    return matching[-limit:]


def list_series() -> list[tuple[str, str]]:
    """Distinct (symbol, timeframe) pairs in the warehouse."""
    found: set[tuple[str, str]] = set()
    try:
        Session = _session_factory()
        if Session is not None:
            with Session() as session:
                rows = session.execute(
                    select(OhlcvBarModel.symbol, OhlcvBarModel.timeframe).distinct()
                ).all()
            found.update((str(sym).upper(), str(tf)) for sym, tf in rows)
    except Exception:
        logger.debug("ohlcv warehouse list skipped", exc_info=True)
    with _lock:
        found.update((sym, tf) for (sym, tf, _ts) in _memory)
    return sorted(found)


def bars_to_frame(bars: list[OhlcvBar]) -> pd.DataFrame:
    """Warehouse bars → engine OHLCV frame."""
    if not bars:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "timestamp": bar.ts,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
    )


def backend_name() -> str:
    try:
        if _session_factory() is not None:
            return "postgres"
    except Exception:
        pass
    return "memory"


def warehouse_status() -> dict[str, object]:
    """Public ops snapshot: backend, table, bar counts. Fail-open."""
    status: dict[str, object] = {
        "backend": "memory",
        "table_present": False,
        "bar_count": 0,
        "symbol_count": 0,
        "latest_ts": None,
    }
    try:
        Session = _session_factory()
    except Exception:
        Session = None
    if Session is not None:
        try:
            from sqlalchemy import distinct, func

            with Session() as session:
                bar_count = int(
                    session.scalar(select(func.count()).select_from(OhlcvBarModel)) or 0
                )
                symbol_count = int(
                    session.scalar(select(func.count(distinct(OhlcvBarModel.symbol)))) or 0
                )
                latest = session.scalar(select(func.max(OhlcvBarModel.ts)))
            status.update(
                {
                    "backend": "postgres",
                    "table_present": True,
                    "bar_count": bar_count,
                    "symbol_count": symbol_count,
                    "latest_ts": _normalize_ts(latest) if latest is not None else None,
                }
            )
            return status
        except Exception:
            logger.debug("ohlcv warehouse status skipped", exc_info=True)

    with _lock:
        bars = list(_memory.values())
    latest_mem = max((bar.ts for bar in bars), default=None)
    status.update(
        {
            "backend": "memory",
            "table_present": False,
            "bar_count": len(bars),
            "symbol_count": len({bar.symbol for bar in bars}),
            "latest_ts": latest_mem,
        }
    )
    return status
