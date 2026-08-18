"""Paper crypto-perps v2 — momentum + funding depth + F&G + Reddit cache."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime

from app.engines.paper_agent.types import PaperDirection
from app.engines.runner_engine.crypto_learn import get_crypto_learn_coefficients
from app.engines.sentiment_engine.engine import fetch_fear_greed
from app.engines.sentiment_engine.reddit_social import analyze_reddit_social
from app.market_data.providers.bybit_derivatives import (
    fetch_derivatives_depth,
    oi_change_pct,
)
from app.market_data.service import MarketDataService
from app.utils.scoring_helpers import clamp_score

logger = logging.getLogger(__name__)

SETUP_TYPE = "perp_momentum"
MIN_CONFIDENCE = 55.0

# Focused slice — keeps discover under the 90s paper cadence.
# Same source of truth as Radar futures + perps board funding.
V2_UNIVERSE: tuple[str, ...] = (
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "AVAX",
    "LINK",
    "DOGE",
    "NEAR",
    "ARB",
    "APT",
    "INJ",
    "OP",
    "SUI",
    "ADA",
    "LTC",
    "DOT",
)

_MOMENTUM_BARS = 12  # ~12h on 1h candles
# safe_get_ohlcv always validates min_rows=20 — never request fewer.
_OHLCV_LIMIT = max(20, _MOMENTUM_BARS + 8)
_SCAN_WORKERS = 6


@dataclass(frozen=True)
class CryptoPerpV2Idea:
    """One paper-perp candidate from the v2 stack."""

    symbol: str
    direction: PaperDirection
    setup_type: str
    confidence: float
    factors: list[str]


def _momentum_pct(market: MarketDataService, symbol: str) -> float | None:
    df = market.safe_get_ohlcv(symbol, "1h", limit=_OHLCV_LIMIT)
    if df is None or len(df) < _MOMENTUM_BARS + 1:
        return None
    closes = df["close"]
    start = float(closes.iloc[-(_MOMENTUM_BARS + 1)])
    end = float(closes.iloc[-1])
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def _direction_from_momentum(mom_pct: float) -> PaperDirection | None:
    floor = get_crypto_learn_coefficients().v2_min_momentum_pct
    if mom_pct >= floor:
        return "long"
    if mom_pct <= -floor:
        return "short"
    return None


def _funding_tilt(
    direction: PaperDirection,
    funding_bps: float | None,
    oi_delta: float | None,
) -> tuple[float, list[str], list[str]]:
    """Return (rule_delta, factors, conflicts) for funding vs momentum."""
    coeffs = get_crypto_learn_coefficients()
    factors: list[str] = []
    conflicts: list[str] = []
    delta = 0.0

    if funding_bps is None:
        conflicts.append("Funding unavailable")
        return -4.0, factors, conflicts

    factors.append(f"Funding {funding_bps:+.2f} bps")
    abs_bps = abs(funding_bps)

    if direction == "long":
        if funding_bps >= coeffs.funding_extreme_bps:
            conflicts.append("Crowded long funding fights momentum long")
            delta -= 14.0
        elif funding_bps >= coeffs.funding_soft_bps:
            conflicts.append("Elevated long funding")
            delta -= 6.0
        elif funding_bps <= -coeffs.funding_soft_bps:
            factors.append("Negative funding supports long")
            delta += 8.0
    else:
        if funding_bps <= -coeffs.funding_extreme_bps:
            conflicts.append("Crowded short funding fights momentum short")
            delta -= 14.0
        elif funding_bps <= -coeffs.funding_soft_bps:
            conflicts.append("Elevated short funding")
            delta -= 6.0
        elif funding_bps >= coeffs.funding_soft_bps:
            factors.append("Positive funding supports short")
            delta += 8.0

    if oi_delta is not None:
        factors.append(f"OI Δ {oi_delta:+.1f}%")
        if abs_bps >= coeffs.funding_extreme_bps and oi_delta >= 3.0:
            conflicts.append("OI rising with extreme funding")
            delta -= coeffs.v2_crowded_oi_penalty
        elif oi_delta <= -5.0:
            factors.append("OI unwinding")
            delta += 3.0

    return delta, factors, conflicts


def _fng_tilt(direction: PaperDirection) -> tuple[float, list[str]]:
    fng = fetch_fear_greed()
    if fng is None:
        return 0.0, ["F&G unavailable — soft neutral"]
    value, classification = fng
    factors = [f"F&G {value} ({classification})"]
    delta = 0.0
    if direction == "long":
        if value <= 40:
            delta += 6.0
            factors.append("Fear zone soft-supports long")
        elif value >= 70:
            delta -= 8.0
            factors.append("Greed zone soft-conflicts long")
    else:
        if value >= 60:
            delta += 6.0
            factors.append("Greed zone soft-supports short")
        elif value <= 30:
            delta -= 8.0
            factors.append("Fear zone soft-conflicts short")
    return delta, factors


def _reddit_tilt(symbol: str, direction: PaperDirection) -> tuple[float, list[str]]:
    try:
        reddit = analyze_reddit_social(symbol, allow_live=False)
    except Exception:
        logger.debug("Reddit cache read failed for %s", symbol, exc_info=True)
        return 0.0, []

    if not reddit.available:
        return 0.0, []

    factors = [reddit.description]
    lean = reddit.lean  # -1 … +1
    if direction == "long":
        if lean >= 0.15:
            return 5.0, factors
        if lean <= -0.15:
            return -5.0, factors
    else:
        if lean <= -0.15:
            return 5.0, factors
        if lean >= 0.15:
            return -5.0, factors
    return 0.0, factors


def score_symbol(
    market: MarketDataService,
    symbol: str,
    *,
    as_of: datetime | None = None,
) -> CryptoPerpV2Idea | None:
    """Score one symbol; None when flat or below confidence floor."""
    del as_of  # reserved for future fingerprinting / audits
    normalized = symbol.upper()
    mom = _momentum_pct(market, normalized)
    if mom is None:
        return None
    direction = _direction_from_momentum(mom)
    if direction is None:
        return None

    coeffs = get_crypto_learn_coefficients()
    factors: list[str] = [f"12h momentum {mom:+.1f}%"]
    conflicts: list[str] = []
    rule = 52.0 + min(abs(mom), 12.0) * coeffs.v2_mom_mult  # ~55 at 1.5%, ~76 at 12%

    depth = fetch_derivatives_depth(normalized)
    funding_bps: float | None = None
    oi_delta: float | None = None
    if depth is not None and depth.funding_rate is not None:
        funding_bps = depth.funding_rate * 10_000
        oi_delta = oi_change_pct(depth.oi_history)

    if (
        coeffs.skip_crowded_opens
        and funding_bps is not None
        and abs(funding_bps) >= coeffs.funding_extreme_bps
    ):
        return None

    fund_delta, fund_factors, fund_conflicts = _funding_tilt(direction, funding_bps, oi_delta)
    rule += fund_delta
    factors.extend(fund_factors)
    conflicts.extend(fund_conflicts)

    fng_delta, fng_factors = _fng_tilt(direction)
    rule += fng_delta
    factors.extend(fng_factors)

    reddit_delta, reddit_factors = _reddit_tilt(normalized, direction)
    rule += reddit_delta
    factors.extend(reddit_factors)

    # Conflict drag — keep explainable and capped
    rule -= min(len(conflicts), 3) * 3.0
    confidence = clamp_score(rule)
    floor = coeffs.min_confidence
    if confidence < floor:
        return None

    return CryptoPerpV2Idea(
        symbol=normalized,
        direction=direction,
        setup_type=SETUP_TYPE,
        confidence=confidence,
        factors=[*factors[:5], *conflicts[:2]],
    )


def scan_crypto_perp_v2(
    market: MarketDataService,
    *,
    symbols: tuple[str, ...] | None = None,
    min_confidence: float | None = None,
) -> list[CryptoPerpV2Idea]:
    """Scan the v2 universe; highest confidence first."""
    universe = symbols or V2_UNIVERSE
    floor = (
        min_confidence
        if min_confidence is not None
        else get_crypto_learn_coefficients().min_confidence
    )
    now = datetime.now(UTC)
    ideas: list[CryptoPerpV2Idea] = []

    def _one(sym: str) -> CryptoPerpV2Idea | None:
        try:
            return score_symbol(market, sym, as_of=now)
        except Exception:
            logger.exception("crypto_perp_v2 score failed for %s", sym)
            return None

    workers = min(_SCAN_WORKERS, max(1, len(universe)))
    if len(universe) <= 1:
        results = [_one(universe[0])] if universe else []
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_one, universe))

    for idea in results:
        if idea is None:
            continue
        if idea.confidence < floor:
            continue
        ideas.append(idea)

    ideas.sort(key=lambda i: i.confidence, reverse=True)
    return ideas
