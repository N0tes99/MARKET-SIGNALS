"""CME / traditional futures scanner — Yahoo continuous contracts, not crypto perps."""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from app.core.process_limits import SCAN_WORKERS
from app.engines.runner_engine.scoring.yahoo_futures_quote import (
    YahooFuturesQuote,
    fetch_yahoo_futures_quote,
)
from app.market_data.providers.cftc_cot import CotEffect, fetch_cot_snapshot, overlay_for_direction
from app.market_data.service import MarketDataService
from app.market_data.symbols import FUTURES_BY_SYMBOL, FUTURES_CONTRACTS, FuturesSpec
from app.schemas.cme_futures import (
    CmeFuturesBoardSchema,
    CmeFuturesRowSchema,
    CmeFuturesUniverseItem,
)
from app.utils.disk_cache import read_json, write_json
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

CmeFuturesBucket = Literal["trending", "extended", "quiet"]

CME_FUTURES_UNIVERSE: tuple[FuturesSpec, ...] = FUTURES_CONTRACTS

_MOM_12H_BARS = 12
_OHLCV_1H_LIMIT = max(20, _MOM_12H_BARS + 8)
_OHLCV_1D_LIMIT = 28
_SCAN_WORKERS = SCAN_WORKERS
_STRONG_MOM_12H = 1.5
_STRONG_MOM_20D = 6.0
_SOFT_MOM_12H = 0.6
_EXTENDED_20D = 10.0
_TRENDING_SCORE_FLOOR = 55.0
_EXTENDED_SCORE_FLOOR = 50.0
_CACHE: TTLCache[list[CmeFuturesRow]] = TTLCache(ttl_seconds=90.0)
_ROW_SCHEMA_LIST = TypeAdapter(list[CmeFuturesRowSchema])


def _disk_path() -> Path:
    return Path(os.environ.get("CME_FUTURES_DISK_CACHE_PATH", "/tmp/se_cme_futures_board.json"))


def _full_cache_key() -> str:
    return ",".join(spec.symbol for spec in CME_FUTURES_UNIVERSE)


@dataclass(frozen=True)
class CmeFuturesRow:
    """One Yahoo continuous futures candidate."""

    id: str
    symbol: str
    name: str
    group: str
    bucket: CmeFuturesBucket
    score: float
    last: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    expiry: date | None = None
    mom_12h_pct: float | None = None
    mom_20d_pct: float | None = None
    relative_volume: float | None = None
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    cot_index: float | None = None
    cot_as_of: date | None = None
    cot_spec_net: float | None = None
    cot_effect: CotEffect | None = None


def _pct_change(start: float, end: float) -> float | None:
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def _mom_12h(market: MarketDataService, symbol: str) -> float | None:
    df = market.safe_get_ohlcv(symbol, "1h", limit=_OHLCV_1H_LIMIT)
    if df is None or len(df) < _MOM_12H_BARS + 1:
        return None
    closes = df["close"]
    return _pct_change(
        float(closes.iloc[-(_MOM_12H_BARS + 1)]),
        float(closes.iloc[-1]),
    )


def _daily_frame(market: MarketDataService, symbol: str):
    return market.safe_get_ohlcv(symbol, "1d", limit=_OHLCV_1D_LIMIT)


def _mom_20d(market: MarketDataService, symbol: str, daily=None) -> float | None:
    df = daily if daily is not None else _daily_frame(market, symbol)
    if df is None or len(df) < 21:
        return None
    closes = df["close"]
    return _pct_change(float(closes.iloc[-21]), float(closes.iloc[-1]))


def _rel_vol(daily, last_volume: float | None) -> float | None:
    if daily is None or len(daily) < 6 or "volume" not in daily.columns:
        return None
    vols = daily["volume"].astype(float)
    avg = float(vols.iloc[:-1].tail(20).mean()) if len(vols) > 1 else float(vols.mean())
    if avg <= 0:
        return None
    last = last_volume
    if last is None or last < 0:
        last = float(vols.iloc[-1])
    if last < 0:
        return None
    return last / avg


def _last_bar_volume(daily) -> float | None:
    if daily is None or daily.empty or "volume" not in daily.columns:
        return None
    try:
        value = float(daily["volume"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    return value if value >= 0 else None


def _last_close(daily) -> float | None:
    if daily is None or daily.empty or "close" not in daily.columns:
        return None
    try:
        value = float(daily["close"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    return value if value > 0 else None


def _session_change_from_daily(daily, last: float | None) -> float | None:
    if daily is None or len(daily) < 2 or "close" not in daily.columns:
        return None
    try:
        prev = float(daily["close"].iloc[-2])
        end = last if last is not None else float(daily["close"].iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    return _pct_change(prev, end)


def _schema_from_row(row: CmeFuturesRow) -> CmeFuturesRowSchema:
    return CmeFuturesRowSchema.model_validate(row, from_attributes=True)


def _row_from_schema(item: CmeFuturesRowSchema) -> CmeFuturesRow:
    return CmeFuturesRow(**item.model_dump())


def _persist_rows(rows: list[CmeFuturesRow]) -> None:
    payload = _ROW_SCHEMA_LIST.dump_python(
        [_schema_from_row(row) for row in rows],
        mode="json",
    )
    write_json(_disk_path(), payload)


def _read_disk_rows() -> list[CmeFuturesRow] | None:
    raw = read_json(_disk_path())
    if raw is None:
        return None
    try:
        items = _ROW_SCHEMA_LIST.validate_python(raw)
    except Exception:
        logger.exception("Invalid CME futures disk cache at %s", _disk_path())
        return None
    return [_row_from_schema(item) for item in items]


def classify_bucket(
    *,
    score: float,
    mom_12h: float | None,
    mom_20d: float | None,
) -> CmeFuturesBucket:
    """Futures-only buckets: trending / extended / quiet. No funding crowded."""
    abs_12 = abs(mom_12h) if mom_12h is not None else 0.0
    abs_20 = abs(mom_20d) if mom_20d is not None else 0.0
    stretched = abs_20 >= _EXTENDED_20D
    fading = mom_12h is not None and abs_12 < _SOFT_MOM_12H

    if stretched and fading and score >= _EXTENDED_SCORE_FLOOR:
        return "extended"
    if stretched and abs_12 >= 2.5 and score >= _EXTENDED_SCORE_FLOOR:
        return "extended"

    strong = abs_12 >= _STRONG_MOM_12H or (
        abs_20 >= _STRONG_MOM_20D and abs_12 >= _SOFT_MOM_12H
    )
    if strong and score >= _TRENDING_SCORE_FLOOR:
        return "trending"
    return "quiet"


def score_symbol(
    market: MarketDataService,
    symbol: str,
    *,
    as_of: datetime | None = None,
    quote: YahooFuturesQuote | None = None,
) -> CmeFuturesRow:
    """Score one Yahoo continuous futures root."""
    normalized = symbol.upper().strip()
    spec = FUTURES_BY_SYMBOL.get(normalized)
    name = spec.name if spec is not None else normalized
    group = spec.group.value if spec is not None else "index"
    now = as_of or datetime.now(UTC)
    factors: list[str] = []
    conflicts: list[str] = []
    rule = 48.0

    snap = quote if quote is not None else fetch_yahoo_futures_quote(normalized)
    daily = _daily_frame(market, normalized)

    last = snap.last
    if last is None:
        last = _last_close(daily)
    if last is None:
        conflicts.append("Last unavailable")

    change_pct = snap.change_pct
    if change_pct is None:
        change_pct = _session_change_from_daily(daily, last)
    if change_pct is not None:
        factors.append(f"Session {change_pct:+.2f}%")

    volume = snap.volume if snap.volume is not None else _last_bar_volume(daily)
    if volume is None:
        conflicts.append("Volume unavailable")

    oi = snap.open_interest
    expiry = snap.expire_date
    if oi is not None:
        factors.append("OI present")
        rule += 2.0

    mom_12h = _mom_12h(market, normalized)
    mom_20d = _mom_20d(market, normalized, daily)
    rel_vol = _rel_vol(daily, volume)

    if mom_12h is not None:
        factors.append(f"12h {mom_12h:+.1f}%")
        rule += min(abs(mom_12h), 8.0) * 2.0
    else:
        conflicts.append("12h momentum unavailable")

    if mom_20d is not None:
        factors.append(f"20d {mom_20d:+.1f}%")
        rule += min(abs(mom_20d), 20.0) * 0.6
        if mom_12h is not None and mom_12h * mom_20d > 0 and abs(mom_12h) >= _SOFT_MOM_12H:
            factors.append("Multi-horizon momentum aligned")
            rule += 4.0
        elif mom_12h is not None and mom_12h * mom_20d < 0 and abs(mom_12h) >= 0.8:
            conflicts.append("12h fights 20d trend")
            rule -= 4.0
    else:
        conflicts.append("20d momentum unavailable")

    if rel_vol is not None:
        factors.append(f"Rel vol {rel_vol:.2f}x")
        if rel_vol >= 1.8:
            rule += 8.0
        elif rel_vol >= 1.3:
            rule += 4.0
        elif rel_vol < 0.6:
            rule -= 3.0
    else:
        conflicts.append("Relative volume unavailable")

    rule -= min(len(conflicts), 3) * 2.0

    tape_dir: str | None = None
    tape = mom_12h if mom_12h is not None else change_pct
    if tape is not None and tape > 0:
        tape_dir = "long"
    elif tape is not None and tape < 0:
        tape_dir = "short"

    cot = fetch_cot_snapshot(normalized)
    cot_index = None
    cot_as_of = None
    cot_spec_net = None
    cot_effect: CotEffect | None = None
    if cot is not None:
        cot_index = cot.cot_index
        cot_as_of = cot.report_date
        cot_spec_net = cot.spec_net
        if oi is None and cot.open_interest is not None:
            oi = cot.open_interest
            factors.append(f"Weekly COT OI as-of {cot.report_date.isoformat()}")
            rule += 2.0
        overlay = overlay_for_direction(tape_dir, cot)
        cot_effect = overlay.effect
        if overlay.factor:
            factors.append(overlay.factor)
        if overlay.conflict:
            conflicts.insert(0, overlay.conflict)
        rule += overlay.delta

    score = clamp_score(rule)
    bucket = classify_bucket(score=score, mom_12h=mom_12h, mom_20d=mom_20d)

    return CmeFuturesRow(
        id=f"cme-futures:{normalized}",
        symbol=normalized,
        name=name,
        group=group,
        bucket=bucket,
        score=score,
        last=last,
        change_pct=round(change_pct, 4) if change_pct is not None else None,
        volume=volume,
        open_interest=oi,
        expiry=expiry,
        mom_12h_pct=mom_12h,
        mom_20d_pct=mom_20d,
        relative_volume=round(rel_vol, 3) if rel_vol is not None else None,
        factors=factors[:8],
        conflicts=conflicts[:4],
        as_of=now,
        cot_index=cot_index,
        cot_as_of=cot_as_of,
        cot_spec_net=cot_spec_net,
        cot_effect=cot_effect,
    )


def _stub_row(spec: FuturesSpec, now: datetime) -> CmeFuturesRow:
    return CmeFuturesRow(
        id=f"cme-futures:{spec.symbol}",
        symbol=spec.symbol,
        name=spec.name,
        group=spec.group.value,
        bucket="quiet",
        score=40.0,
        conflicts=["Yahoo snapshot unavailable"],
        as_of=now,
    )


def scan_cme_futures(
    market: MarketDataService | None = None,
    *,
    symbols: tuple[str, ...] | None = None,
    use_cache: bool = True,
    sync: bool = False,
) -> list[CmeFuturesRow]:
    """Scan the CME Yahoo universe; highest score first.

    Cached scans use stale-while-revalidate so ``GET /futures/board`` never
    blocks on Yahoo when a last-good payload exists. ``sync=True`` forces a
    fresh fill (keep-warm).
    """
    md = market or MarketDataService()
    specs = (
        tuple(FUTURES_BY_SYMBOL[s.upper()] for s in symbols if s.upper() in FUTURES_BY_SYMBOL)
        if symbols is not None
        else CME_FUTURES_UNIVERSE
    )
    cache_key = ",".join(s.symbol for s in specs)
    persist = cache_key == _full_cache_key()

    def _load() -> list[CmeFuturesRow]:
        now = datetime.now(UTC)
        rows: list[CmeFuturesRow] = []

        def _one(spec: FuturesSpec) -> CmeFuturesRow:
            try:
                return score_symbol(md, spec.symbol, as_of=now)
            except Exception:
                logger.exception("CME futures score failed for %s", spec.symbol)
                return _stub_row(spec, now)

        workers = min(_SCAN_WORKERS, max(1, len(specs)))
        if len(specs) <= 1:
            results = [_one(specs[0])] if specs else []
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_one, specs))

        rows.extend(results)
        rows.sort(key=lambda r: r.score, reverse=True)
        if persist:
            _persist_rows(rows)
        return rows

    if not use_cache:
        return _load()

    if sync:
        rows = _load()
        _CACHE.set(cache_key, rows)
        return list(rows)

    cached, _, _, _ = _CACHE.meta(cache_key)
    if cached is None:
        disk = _read_disk_rows() if persist else None
        # Seed stale so SWR returns immediately and refreshes in background.
        _CACHE.seed_stale(cache_key, disk if disk else [])

    return list(_CACHE.get_stale_while_revalidate(cache_key, _load))


def build_cme_futures_board(
    market: MarketDataService | None = None,
    *,
    use_cache: bool = True,
    sync: bool = False,
) -> CmeFuturesBoardSchema:
    """API payload for GET /futures/board."""
    rows = scan_cme_futures(market, use_cache=use_cache, sync=sync)
    scanned_at = rows[0].as_of if rows else datetime.now(UTC)
    return CmeFuturesBoardSchema(
        rows=[_schema_from_row(row) for row in rows],
        scanned_at=scanned_at,
        symbols_scanned=len(rows),
        universe=[
            CmeFuturesUniverseItem(symbol=spec.symbol, name=spec.name, group=spec.group.value)
            for spec in CME_FUTURES_UNIVERSE
        ],
        source="yahoo",
    )


def clear_cme_futures_cache() -> None:
    """Test helper."""
    _CACHE.clear()
