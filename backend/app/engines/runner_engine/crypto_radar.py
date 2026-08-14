"""Crypto movers radar — Watch / Crowded / Running from V2 universe."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.engines.paper_agent.crypto_perp_v2 import V2_UNIVERSE
from app.engines.sentiment_engine.engine import fetch_fear_greed
from app.market_data.providers.bybit_derivatives import (
    fetch_derivatives_depth,
    oi_change_pct,
)
from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

CryptoRadarBucket = Literal["watch", "crowded", "running", "none"]

# Same focused slice as paper perp v2.
CRYPTO_RADAR_UNIVERSE: tuple[str, ...] = V2_UNIVERSE

_MOM_12H_BARS = 12
_OHLCV_1H_LIMIT = max(20, _MOM_12H_BARS + 8)
_OHLCV_1D_LIMIT = 28
_FUNDING_EXTREME_BPS = 8.0
_FUNDING_SOFT_BPS = 3.0
_SCAN_WORKERS = 6
_CACHE: TTLCache[list[CryptoRadarCandidate]] = TTLCache(ttl_seconds=90.0)


@dataclass(frozen=True)
class CryptoRadarCandidate:
    """One crypto possible-move candidate for the Radar crypto track."""

    id: str
    symbol: str
    bucket: CryptoRadarBucket
    score: float
    factors: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    mom_12h_pct: float | None = None
    mom_20d_pct: float | None = None
    funding_bps: float | None = None
    oi_change_pct: float | None = None
    funding_source: str = ""
    mark_price: float | None = None
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))


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


def _mom_20d(market: MarketDataService, symbol: str) -> float | None:
    df = market.safe_get_ohlcv(symbol, "1d", limit=_OHLCV_1D_LIMIT)
    if df is None or len(df) < 21:
        return None
    closes = df["close"]
    return _pct_change(float(closes.iloc[-21]), float(closes.iloc[-1]))


def _classify(
    *,
    score: float,
    mom_12h: float | None,
    mom_20d: float | None,
    funding_bps: float | None,
) -> CryptoRadarBucket:
    abs_fund = abs(funding_bps) if funding_bps is not None else 0.0
    abs_12 = abs(mom_12h) if mom_12h is not None else 0.0
    abs_20 = abs(mom_20d) if mom_20d is not None else 0.0

    extreme_fund = abs_fund >= _FUNDING_EXTREME_BPS
    soft_fund = abs_fund >= _FUNDING_SOFT_BPS
    strong_mom = abs_12 >= 4.0 or abs_20 >= 15.0
    soft_mom = abs_12 >= 1.5 or abs_20 >= 8.0

    # Crowded first — crypto-specific positioning lane.
    if extreme_fund and score >= 55.0:
        return "crowded"
    if strong_mom and score >= 60.0:
        return "running"
    if (soft_mom or soft_fund) and score >= 52.0:
        return "watch"
    return "none"


def score_symbol(
    market: MarketDataService,
    symbol: str,
    *,
    as_of: datetime | None = None,
) -> CryptoRadarCandidate:
    """Score one crypto symbol into a radar candidate."""
    normalized = symbol.upper()
    now = as_of or datetime.now(UTC)
    factors: list[str] = []
    conflicts: list[str] = []
    rule = 48.0

    mom_12h = _mom_12h(market, normalized)
    mom_20d = _mom_20d(market, normalized)

    if mom_12h is not None:
        factors.append(f"12h {mom_12h:+.1f}%")
        rule += min(abs(mom_12h), 12.0) * 1.8
    else:
        conflicts.append("12h momentum unavailable")

    if mom_20d is not None:
        factors.append(f"20d {mom_20d:+.1f}%")
        rule += min(abs(mom_20d), 25.0) * 0.35
        # Align 12h and 20d direction when both present
        if mom_12h is not None and mom_12h * mom_20d > 0 and abs(mom_12h) >= 1.5:
            factors.append("Multi-horizon momentum aligned")
            rule += 4.0
        elif mom_12h is not None and mom_12h * mom_20d < 0 and abs(mom_12h) >= 2.0:
            conflicts.append("12h fights 20d trend")
            rule -= 5.0

    funding_bps: float | None = None
    oi_delta: float | None = None
    funding_source = ""
    mark: float | None = None
    depth = fetch_derivatives_depth(normalized)
    if depth is not None and depth.funding_rate is not None:
        funding_bps = depth.funding_rate * 10_000
        oi_delta = oi_change_pct(depth.oi_history)
        funding_source = depth.source or ""
        mark = depth.mark_price
        factors.append(f"Funding {funding_bps:+.2f} bps [{funding_source}]")
        abs_bps = abs(funding_bps)
        if abs_bps >= _FUNDING_EXTREME_BPS:
            factors.append("Extreme funding crowding")
            rule += 10.0
        elif abs_bps >= _FUNDING_SOFT_BPS:
            factors.append("Elevated funding")
            rule += 4.0
        if oi_delta is not None:
            factors.append(f"OI Δ {oi_delta:+.1f}%")
            if abs_bps >= _FUNDING_EXTREME_BPS and oi_delta >= 3.0:
                conflicts.append("OI rising with extreme funding")
                rule -= 3.0
            elif oi_delta <= -5.0:
                factors.append("OI unwinding")
                rule += 3.0
    else:
        conflicts.append("Funding unavailable")
        rule -= 4.0

    fng = fetch_fear_greed()
    if fng is not None:
        value, classification = fng
        factors.append(f"F&G {value} ({classification})")
        if value <= 30 or value >= 70:
            rule += 2.0

    rule -= min(len(conflicts), 3) * 2.5
    score = clamp_score(rule)
    bucket = _classify(
        score=score,
        mom_12h=mom_12h,
        mom_20d=mom_20d,
        funding_bps=funding_bps,
    )

    return CryptoRadarCandidate(
        id=f"crypto-radar:{normalized}",
        symbol=normalized,
        bucket=bucket,
        score=score,
        factors=factors[:6],
        conflicts=conflicts[:3],
        mom_12h_pct=mom_12h,
        mom_20d_pct=mom_20d,
        funding_bps=round(funding_bps, 3) if funding_bps is not None else None,
        oi_change_pct=round(oi_delta, 2) if oi_delta is not None else None,
        funding_source=funding_source,
        mark_price=mark,
        as_of=now,
    )


def scan_crypto_radar(
    market: MarketDataService | None = None,
    *,
    symbols: tuple[str, ...] | None = None,
    use_cache: bool = True,
) -> list[CryptoRadarCandidate]:
    """Scan crypto radar universe; highest score first."""
    md = market or MarketDataService()
    universe = symbols or CRYPTO_RADAR_UNIVERSE
    cache_key = ",".join(universe)

    def _load() -> list[CryptoRadarCandidate]:
        now = datetime.now(UTC)
        ideas: list[CryptoRadarCandidate] = []

        def _one(sym: str) -> CryptoRadarCandidate | None:
            try:
                return score_symbol(md, sym, as_of=now)
            except Exception:
                logger.exception("crypto radar score failed for %s", sym)
                return None

        workers = min(_SCAN_WORKERS, max(1, len(universe)))
        if len(universe) <= 1:
            results = [_one(universe[0])] if universe else []
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(_one, universe))

        for idea in results:
            if idea is not None:
                ideas.append(idea)
        ideas.sort(key=lambda c: c.score, reverse=True)
        return ideas

    if use_cache:
        return list(_CACHE.get_or_set(cache_key, _load))
    return _load()


def crypto_radar_lists(
    market: MarketDataService | None = None,
    *,
    symbols: tuple[str, ...] | None = None,
) -> dict[str, list[CryptoRadarCandidate]]:
    """Return Watch / Crowded / Running buckets."""
    all_cands = scan_crypto_radar(market, symbols=symbols, use_cache=True)
    return {
        "watch": [c for c in all_cands if c.bucket == "watch"],
        "crowded": [c for c in all_cands if c.bucket == "crowded"],
        "running": [c for c in all_cands if c.bucket == "running"],
        "all": all_cands,
    }


def clear_crypto_radar_cache() -> None:
    """Test helper."""
    _CACHE.clear()
