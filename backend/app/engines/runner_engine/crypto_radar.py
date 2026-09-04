"""Crypto movers radar — Watch / Crowded / Running from V2 universe."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.core.process_limits import SCAN_WORKERS
from app.engines.paper_agent.crypto_perp_v2 import V2_UNIVERSE
from app.engines.runner_engine.crypto_learn import get_crypto_learn_coefficients
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
_SCAN_WORKERS = SCAN_WORKERS
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
    basis_pct: float | None = None
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


def _spot_price(market: MarketDataService, symbol: str) -> float | None:
    try:
        ticker = market.get_ticker(symbol)
    except Exception:
        return None
    price = getattr(ticker, "price", None)
    if price is None:
        return None
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _basis_pct(
    market: MarketDataService,
    symbol: str,
    mark: float | None,
) -> float | None:
    """Mark vs spot, percent. Missing either side → skip."""
    if mark is None or mark <= 0:
        return None
    spot = _spot_price(market, symbol)
    if spot is None or spot <= 0:
        return None
    return ((mark - spot) / spot) * 100.0


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

    coeffs = get_crypto_learn_coefficients()
    extreme_fund = abs_fund >= coeffs.funding_extreme_bps
    soft_fund = abs_fund >= coeffs.funding_soft_bps
    strong_mom = abs_12 >= coeffs.strong_mom_12h or abs_20 >= coeffs.strong_mom_20d
    soft_mom = abs_12 >= coeffs.soft_mom_12h or abs_20 >= coeffs.soft_mom_20d

    # Crowded first — crypto-specific positioning lane.
    if extreme_fund and score >= coeffs.crowded_score_floor:
        return "crowded"
    if strong_mom and score >= coeffs.running_score_floor:
        return "running"
    if (soft_mom or soft_fund) and score >= coeffs.watch_score_floor:
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
    coeffs = get_crypto_learn_coefficients()
    factors: list[str] = []
    conflicts: list[str] = []
    rule = 48.0

    mom_12h = _mom_12h(market, normalized)
    mom_20d = _mom_20d(market, normalized)

    if mom_12h is not None:
        factors.append(f"12h {mom_12h:+.1f}%")
        rule += min(abs(mom_12h), 12.0) * coeffs.radar_mom_12h_mult
    else:
        conflicts.append("12h momentum unavailable")

    if mom_20d is not None:
        factors.append(f"20d {mom_20d:+.1f}%")
        rule += min(abs(mom_20d), 25.0) * coeffs.radar_mom_20d_mult
        # Align 12h and 20d direction when both present
        if mom_12h is not None and mom_12h * mom_20d > 0 and abs(mom_12h) >= coeffs.soft_mom_12h:
            factors.append("Multi-horizon momentum aligned")
            rule += coeffs.radar_mom_align_bonus
        elif mom_12h is not None and mom_12h * mom_20d < 0 and abs(mom_12h) >= 2.0:
            conflicts.append("12h fights 20d trend")
            rule -= coeffs.radar_mom_fight_penalty

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
        if abs_bps >= coeffs.funding_extreme_bps:
            factors.append("Extreme funding crowding")
            rule += 10.0
        elif abs_bps >= coeffs.funding_soft_bps:
            factors.append("Elevated funding")
            rule += 4.0
        if oi_delta is not None:
            factors.append(f"OI Δ {oi_delta:+.1f}%")
            if abs_bps >= coeffs.funding_extreme_bps and oi_delta >= 3.0:
                conflicts.append("OI rising with extreme funding")
                rule -= coeffs.crowded_oi_penalty
            elif oi_delta <= -5.0:
                factors.append("OI unwinding")
                rule += 3.0
    else:
        conflicts.append("Funding unavailable")
        rule -= 4.0

    basis_pct = _basis_pct(market, normalized, mark)
    if basis_pct is not None:
        factors.append(f"Basis {basis_pct:+.3f}%")
        rule += min(abs(basis_pct), 1.5) * coeffs.basis_weight

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
        factors=factors[:7],
        conflicts=conflicts[:3],
        mom_12h_pct=mom_12h,
        mom_20d_pct=mom_20d,
        funding_bps=round(funding_bps, 3) if funding_bps is not None else None,
        oi_change_pct=round(oi_delta, 2) if oi_delta is not None else None,
        funding_source=funding_source,
        mark_price=mark,
        basis_pct=round(basis_pct, 4) if basis_pct is not None else None,
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
