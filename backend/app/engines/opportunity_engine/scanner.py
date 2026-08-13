"""Setup scanners — second surface for crypto opportunity ideas.

Reads derivatives / market data outputs. Does not invent prices.
Does not fold into the 13-category asset grade or OpportunityEngine ranking.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from uuid import uuid4

from app.engines.opportunity_engine.types import (
    DataQuality,
    DirectionBias,
    OpportunityIdea,
    TradeStateHint,
)
from app.market_data.providers.bybit_derivatives import (
    DerivativesDepth,
    fetch_derivatives_depth,
    oi_change_pct,
)
from app.market_data.providers.coinglass import (
    LiquidationSnapshot,
    fetch_aggregated_liquidations,
)
from app.market_data.service import MarketDataService
from app.market_data.symbols import CRYPTO_SYMBOLS, AssetClass, get_asset_class
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

# Confidence thresholds for WATCH vs IGNORE (never EXECUTE in MVP).
_WATCH_MIN_CONFIDENCE = 55.0

# funding_extreme: elevated crowding
_FUNDING_EXTREME_BPS = 8.0  # |funding| in bps
_FUNDING_SOFT_BPS = 5.0
_OI_CROWD_PCT = 3.0

# liq_flush: imbalance + meaningful size
_LIQ_LONG_SHARE_HIGH = 0.62
_LIQ_LONG_SHARE_LOW = 0.38
_LIQ_MIN_TOTAL_USD = 2_500_000.0

# basis_rich: mark vs spot (annualized not required for MVP)
_BASIS_RICH_PCT = 0.15  # |mark-spot|/spot * 100
_BASIS_SOFT_PCT = 0.08

_SCAN_CACHE: TTLCache[list[OpportunityIdea]] = TTLCache(ttl_seconds=90.0)
_FEED_CACHE: TTLCache[list[OpportunityIdea]] = TTLCache(ttl_seconds=90.0)
_FEED_MAX_WORKERS = 6


def _hint(confidence: float) -> TradeStateHint:
    return "WATCH" if confidence >= _WATCH_MIN_CONFIDENCE else "IGNORE"


def _idea_id(symbol: str, setup_type: str) -> str:
    return f"{symbol.lower()}-{setup_type}-{uuid4().hex[:8]}"


def _freshness_factor(*, depth_ok: bool, liq_ok: bool | None = None) -> float:
    """1.0 when primary feed present; soft-degrade when partial."""
    if liq_ok is None:
        return 1.0 if depth_ok else 0.55
    if depth_ok and liq_ok:
        return 1.0
    if depth_ok or liq_ok:
        return 0.75
    return 0.45


def _agreement_factor(factor_count: int, conflict_count: int) -> float:
    """Multi-factor agreement bonus; conflicts reduce."""
    base = 0.7 + min(factor_count, 3) * 0.1
    penalty = min(conflict_count, 3) * 0.12
    return max(0.35, base - penalty)


def _compose_confidence(
    rule_score: float,
    *,
    freshness: float,
    factor_count: int,
    conflict_count: int,
) -> float:
    """Explainable clamp: rule × freshness × agreement − conflict drag."""
    agreement = _agreement_factor(factor_count, conflict_count)
    raw = rule_score * freshness * agreement - conflict_count * 4.0
    return clamp_score(raw)


def scan_funding_extreme(
    symbol: str,
    depth: DerivativesDepth | None,
    as_of: datetime,
) -> OpportunityIdea | None:
    """Extreme funding + crowded OI (when OI Δ available)."""
    if depth is None or depth.funding_rate is None:
        return None

    funding = depth.funding_rate
    funding_bps = funding * 10_000
    abs_bps = abs(funding_bps)
    if abs_bps < _FUNDING_SOFT_BPS:
        return None

    factors: list[str] = [f"Funding {funding_bps:+.2f} bps"]
    conflicts: list[str] = []
    oi_delta = oi_change_pct(depth.oi_history)

    # Direction: crowded longs → short bias; crowded shorts → long bias
    if funding_bps >= _FUNDING_SOFT_BPS:
        direction: DirectionBias = "short"
        factors.append("Longs paying elevated funding (crowded long)")
    else:
        direction = "long"
        factors.append("Shorts paying (negative funding / crowded short)")

    rule = 48.0 + min(abs_bps, 25.0) * 1.4  # ~55 at 5 bps, ~83 at 25 bps

    if oi_delta is not None:
        factors.append(f"OI Δ {oi_delta:+.1f}% over recent window")
        if abs_bps >= _FUNDING_EXTREME_BPS and oi_delta >= _OI_CROWD_PCT:
            rule += 12.0
            factors.append("OI rising with extreme funding (crowding confirmed)")
        elif oi_delta <= -5.0:
            conflicts.append(f"OI already unwinding ({oi_delta:+.1f}%)")
            rule -= 8.0
    else:
        conflicts.append("OI history unavailable — crowding unconfirmed")

    if abs_bps < _FUNDING_EXTREME_BPS:
        # Soft zone: only emit if OI confirms crowding
        if oi_delta is None or oi_delta < _OI_CROWD_PCT:
            return None
        factors.append("Funding moderate; OI crowding carries the setup")

    quality: DataQuality = "good" if oi_delta is not None else "degraded"
    freshness = _freshness_factor(depth_ok=True)
    confidence = _compose_confidence(
        rule,
        freshness=freshness,
        factor_count=len(factors),
        conflict_count=len(conflicts),
    )

    return OpportunityIdea(
        id=_idea_id(symbol, "funding_extreme"),
        symbol=symbol,
        instrument_type="perp",
        setup_type="funding_extreme",
        direction_bias=direction,
        confidence=confidence,
        factors=factors,
        conflicts=conflicts,
        trade_state_hint=_hint(confidence),
        as_of=as_of,
        data_quality=quality,
    )


def scan_liq_flush(
    symbol: str,
    liq: LiquidationSnapshot | None,
    as_of: datetime,
) -> OpportunityIdea | None:
    """Liquidation imbalance / heat from CoinGlass aggregated stats."""
    if liq is None or liq.total_usd < _LIQ_MIN_TOTAL_USD:
        return None

    share = liq.long_share
    if _LIQ_LONG_SHARE_LOW < share < _LIQ_LONG_SHARE_HIGH:
        return None

    factors: list[str] = []
    conflicts: list[str] = []
    size_note = (
        f"${liq.total_usd / 1e6:.1f}M"
        if liq.total_usd >= 1_000_000
        else f"${liq.total_usd / 1e3:.0f}K"
    )
    factors.append(
        f"Liqs {liq.interval} {size_note} "
        f"(L ${liq.long_usd / 1e6:.2f}M / S ${liq.short_usd / 1e6:.2f}M)"
    )

    imbalance = abs(share - 0.5) * 2.0  # 0..1
    if share >= _LIQ_LONG_SHARE_HIGH:
        direction: DirectionBias = "long"
        factors.append("Long liquidations dominant — forced-sell flush")
        rule = 52.0 + imbalance * 28.0
    else:
        direction = "short"
        factors.append("Short liquidations dominant — forced-cover flush")
        rule = 52.0 + imbalance * 28.0

    if liq.total_usd >= 50_000_000:
        rule += 8.0
        factors.append("Large liquidation notional (≥$50M)")
    elif liq.total_usd < 10_000_000:
        conflicts.append("Liquidation notional is modest — noise risk")
        rule -= 6.0

    confidence = _compose_confidence(
        rule,
        freshness=1.0,
        factor_count=len(factors),
        conflict_count=len(conflicts),
    )

    return OpportunityIdea(
        id=_idea_id(symbol, "liq_flush"),
        symbol=symbol,
        instrument_type="perp",
        setup_type="liq_flush",
        direction_bias=direction,
        confidence=confidence,
        factors=factors,
        conflicts=conflicts,
        trade_state_hint=_hint(confidence),
        as_of=as_of,
        data_quality="good",
    )


def scan_basis_rich(
    symbol: str,
    depth: DerivativesDepth | None,
    spot_price: float | None,
    as_of: datetime,
) -> OpportunityIdea | None:
    """Perp mark rich/cheap vs spot — only when both prices are real feeds."""
    if depth is None or depth.mark_price is None or spot_price is None:
        return None
    if spot_price <= 0 or depth.mark_price <= 0:
        return None

    basis_pct = ((depth.mark_price - spot_price) / spot_price) * 100.0
    abs_basis = abs(basis_pct)
    if abs_basis < _BASIS_SOFT_PCT:
        return None

    factors: list[str] = [
        f"Mark {depth.mark_price:,.4f} vs spot {spot_price:,.4f}",
        f"Basis {basis_pct:+.3f}%",
    ]
    conflicts: list[str] = []

    if basis_pct >= _BASIS_SOFT_PCT:
        direction: DirectionBias = "short"
        factors.append("Perp trading rich to spot")
    else:
        direction = "long"
        factors.append("Perp trading cheap to spot")

    rule = 46.0 + min(abs_basis, 1.5) * 22.0  # ~64 at 0.8%, soft at 0.08%

    if abs_basis < _BASIS_RICH_PCT:
        conflicts.append("Basis only mildly elevated — weak setup")
        rule -= 10.0
        # Still emit only if soft zone and not too weak after penalty
        if rule < 45:
            return None
    else:
        factors.append("Basis above rich threshold")

    source = depth.source or "derivatives"
    factors.append(f"Mark source: {source}")

    confidence = _compose_confidence(
        rule,
        freshness=_freshness_factor(depth_ok=True),
        factor_count=len(factors),
        conflict_count=len(conflicts),
    )

    return OpportunityIdea(
        id=_idea_id(symbol, "basis_rich"),
        symbol=symbol,
        instrument_type="perp",
        setup_type="basis_rich",
        direction_bias=direction,
        confidence=confidence,
        factors=factors,
        conflicts=conflicts,
        trade_state_hint=_hint(confidence),
        as_of=as_of,
        data_quality="good",
    )


class SetupScanner:
    """Scan a crypto symbol for setup candidates from live market feeds."""

    def __init__(self, market_data: MarketDataService | None = None) -> None:
        self._market_data = market_data or MarketDataService()

    def scan(self, symbol: str) -> list[OpportunityIdea]:
        """Return zero or more setup ideas. Soft-fails to [] — never raises."""
        normalized = symbol.upper()
        try:
            return _SCAN_CACHE.get_stale_while_revalidate(
                normalized, lambda: self._scan_uncached(normalized)
            )
        except Exception:
            logger.exception("Setup scan failed for %s", normalized)
            return []

    def scan_feed(
        self,
        symbols: Sequence[str] | None = None,
        *,
        watch_only: bool = False,
        min_confidence: float = 0.0,
    ) -> list[OpportunityIdea]:
        """Scan crypto symbols in parallel for the dashboard feed.

        Soft-fails per symbol. Results are sorted WATCH-first, then confidence.
        Aggregated under a short TTL so the dashboard stays snappy.
        """
        universe = tuple(s.upper() for s in (symbols if symbols is not None else CRYPTO_SYMBOLS))
        cache_key = f"feed:{','.join(universe)}"

        def _build() -> list[OpportunityIdea]:
            return self._scan_many_uncached(universe)

        try:
            ideas = _FEED_CACHE.get_stale_while_revalidate(cache_key, _build)
        except Exception:
            logger.exception("Setup feed scan failed")
            ideas = []

        filtered = [
            idea
            for idea in ideas
            if idea.confidence >= min_confidence
            and (not watch_only or idea.trade_state_hint == "WATCH")
        ]
        filtered.sort(
            key=lambda i: (i.trade_state_hint == "WATCH", i.confidence),
            reverse=True,
        )
        return filtered

    def _scan_many_uncached(self, symbols: Sequence[str]) -> list[OpportunityIdea]:
        ideas: list[OpportunityIdea] = []
        if not symbols:
            return ideas

        workers = min(_FEED_MAX_WORKERS, max(1, len(symbols)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.scan, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    ideas.extend(future.result())
                except Exception:
                    logger.exception("Setup feed worker failed for %s", symbol)
        return ideas

    def _scan_uncached(self, symbol: str) -> list[OpportunityIdea]:
        try:
            asset_class = get_asset_class(symbol)
        except ValueError:
            return []

        if asset_class != AssetClass.CRYPTO:
            return []

        as_of = datetime.now(UTC)
        depth: DerivativesDepth | None = None
        liq: LiquidationSnapshot | None = None
        spot: float | None = None

        try:
            depth = fetch_derivatives_depth(symbol)
        except Exception:
            logger.debug("Derivatives depth unavailable for %s", symbol, exc_info=True)

        try:
            liq = fetch_aggregated_liquidations(symbol)
        except Exception:
            logger.debug("Liquidations unavailable for %s", symbol, exc_info=True)

        try:
            ticker = self._market_data.get_ticker(symbol)
            spot = ticker.price
        except Exception:
            logger.debug("Spot ticker unavailable for %s", symbol, exc_info=True)

        ideas: list[OpportunityIdea] = []

        try:
            idea = scan_funding_extreme(symbol, depth, as_of)
            if idea is not None:
                ideas.append(idea)
        except Exception:
            logger.exception("funding_extreme scan error for %s", symbol)

        try:
            idea = scan_liq_flush(symbol, liq, as_of)
            if idea is not None:
                ideas.append(idea)
        except Exception:
            logger.exception("liq_flush scan error for %s", symbol)

        try:
            idea = scan_basis_rich(symbol, depth, spot, as_of)
            if idea is not None:
                ideas.append(idea)
        except Exception:
            logger.exception("basis_rich scan error for %s", symbol)

        # Highest confidence first; empty list is a valid quiet day
        ideas.sort(key=lambda i: i.confidence, reverse=True)
        return ideas
