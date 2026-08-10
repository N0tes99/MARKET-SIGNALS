"""Layer 3 equity-options setup scanner — third surface."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from uuid import uuid4

from app.engines.opportunity_engine.equity_options.momentum import compute_momentum
from app.engines.opportunity_engine.equity_options.option_chain import (
    RawOptionRow,
    fetch_yahoo_option_chain,
)
from app.engines.opportunity_engine.equity_options.option_selector import score_option_candidates
from app.engines.opportunity_engine.equity_options.plan_builder import build_execution_plan
from app.engines.opportunity_engine.equity_options.types import (
    DataQuality,
    DirectionBias,
    EquityOptionsIdea,
    EquitySetupType,
    MomentumSnapshot,
    TradeStateHint,
)
from app.market_data.service import MarketDataService
from app.market_data.symbols import ETF_SYMBOLS, STOCK_SYMBOLS, AssetClass, get_asset_class
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_WATCH_MIN = 55.0
_SCAN_CACHE: TTLCache[list[EquityOptionsIdea]] = TTLCache(ttl_seconds=120.0)
_FEED_CACHE: TTLCache[list[EquityOptionsIdea]] = TTLCache(ttl_seconds=120.0)
_FEED_MAX_WORKERS = 6

OptionChainFetcher = Callable[[str], list[RawOptionRow]]

EQUITY_UNIVERSE: tuple[str, ...] = STOCK_SYMBOLS + ETF_SYMBOLS


def _idea_id(symbol: str, setup_type: str) -> str:
    return f"{symbol.lower()}-{setup_type}-{uuid4().hex[:8]}"


def _hint(confidence: float) -> TradeStateHint:
    return "WATCH" if confidence >= _WATCH_MIN else "IGNORE"


def _direction_from_momentum(snap: MomentumSnapshot) -> DirectionBias:
    if snap.momentum_score >= 58 and snap.structure_score >= 55:
        return "long"
    if snap.momentum_score <= 42 and snap.structure_score <= 45:
        return "short"
    if snap.momentum_score >= 55:
        return "long"
    if snap.momentum_score <= 45:
        return "short"
    return "neutral"


def _setup_type(snap: MomentumSnapshot, direction: DirectionBias) -> EquitySetupType:
    if snap.breakout_level is None:
        return "momentum_continuation"
    dist = abs(snap.breakout_level - snap.price) / snap.price * 100.0
    if direction == "long" and dist <= 3.5 and snap.relative_volume >= 1.2:
        return "breakout_convexity"
    if direction == "short" and snap.support_level is not None:
        dist_sup = abs(snap.price - snap.support_level) / snap.price * 100.0
        if dist_sup <= 3.5 and snap.relative_volume >= 1.2:
            return "breakout_convexity"
    return "momentum_continuation"


def _catalyst_proxy(snap: MomentumSnapshot) -> float:
    """Lightweight catalyst stand-in until event engine is wired into Layer 3."""
    score = 50.0
    if snap.breakout_level and snap.price > 0:
        dist = abs(snap.breakout_level - snap.price) / snap.price * 100.0
        if dist <= 2.0:
            score += 12.0
        elif dist <= 5.0:
            score += 6.0
    if snap.relative_volume >= 1.8:
        score += 10.0
    elif snap.relative_volume >= 1.3:
        score += 5.0
    if snap.atr_pct >= 2.5:
        score += 4.0
    return clamp_score(score)


def build_idea_from_momentum(
    symbol: str,
    snap: MomentumSnapshot,
    option_rows: list[RawOptionRow] | None,
    *,
    as_of: datetime | None = None,
    max_risk_usd: float = 1000.0,
) -> EquityOptionsIdea | None:
    """Compose a Layer 3 idea from momentum + optional option chain."""
    now = as_of or datetime.now(UTC)
    direction = _direction_from_momentum(snap)
    if direction == "neutral":
        return None

    bullish_ok = direction == "long" and snap.momentum_score >= 56
    bearish_ok = direction == "short" and snap.momentum_score <= 44
    if not (bullish_ok or bearish_ok):
        return None

    setup = _setup_type(snap, direction)
    factors = list(snap.factors)
    conflicts = list(snap.conflicts)
    catalyst = _catalyst_proxy(snap)

    rows = option_rows if option_rows is not None else []
    candidates = score_option_candidates(
        symbol,
        snap.price,
        direction,
        rows,
        as_of=now.date(),
    )
    selected = candidates[0] if candidates else None

    quality: DataQuality = "good"
    if option_rows is None:
        quality = "degraded"
        conflicts.append("Option chain unavailable — plan is structure-only")
    elif not candidates:
        quality = "degraded"
        conflicts.append("No suitable OTM option candidates in band")
    else:
        factors.append(
            f"Best option: {selected.expiry} ${selected.strike:.0f} {selected.right} "
            f"(score {selected.overall_score:.0f})"
        )
        if len(candidates) >= 2:
            alt = candidates[1]
            factors.append(
                f"Alt: {alt.expiry} ${alt.strike:.0f} {alt.right} "
                f"(score {alt.overall_score:.0f}) — compare lottery vs risk-adjusted"
            )

    liquidity = selected.liquidity_score if selected else 45.0
    if selected is None:
        liquidity = 40.0

    option_component = selected.overall_score if selected else 48.0
    mom_for_dir = snap.momentum_score if direction == "long" else (100.0 - snap.momentum_score)
    opportunity = clamp_score(
        mom_for_dir * 0.45 + catalyst * 0.20 + option_component * 0.25 + liquidity * 0.10
    )

    rule = opportunity
    rule -= len(conflicts) * 4.0
    rule += min(len(factors), 5) * 1.5
    if quality != "good":
        rule -= 6.0
    confidence = clamp_score(rule)

    plan = build_execution_plan(
        symbol,
        direction,
        snap,
        selected,
        setup_type=setup,
        max_risk_usd=max_risk_usd,
    )

    return EquityOptionsIdea(
        id=_idea_id(symbol, setup),
        symbol=symbol.upper(),
        setup_type=setup,
        direction_bias=direction,
        confidence=confidence,
        opportunity_score=opportunity,
        factors=factors,
        conflicts=conflicts,
        trade_state_hint=_hint(confidence),
        momentum_score=snap.momentum_score,
        catalyst_score=catalyst,
        liquidity_score=liquidity,
        option_candidates=candidates,
        selected_option=selected,
        execution_plan=plan,
        as_of=now,
        data_quality=quality,
    )


class EquityOptionsScanner:
    """Scan equities/ETFs for Layer 3 options setups."""

    def __init__(
        self,
        market_data: MarketDataService,
        *,
        option_fetcher: OptionChainFetcher | None = None,
        max_risk_usd: float = 1000.0,
    ) -> None:
        self._market_data = market_data
        self._option_fetcher = option_fetcher or fetch_yahoo_option_chain
        self._max_risk_usd = max_risk_usd

    def scan(self, symbol: str) -> list[EquityOptionsIdea]:
        """Scan a single symbol; empty for crypto or soft failures."""
        normalized = symbol.upper()
        try:
            return _SCAN_CACHE.get_or_set(
                f"eqopt:{normalized}",
                lambda: self._scan_uncached(normalized),
            )
        except Exception:
            logger.exception("Layer 3 scan failed for %s", normalized)
            return []

    def _scan_uncached(self, symbol: str) -> list[EquityOptionsIdea]:
        try:
            asset_class = get_asset_class(symbol)
        except ValueError:
            return []
        if asset_class not in {AssetClass.STOCK, AssetClass.ETF}:
            return []

        ohlcv = self._market_data.safe_get_ohlcv(symbol, "1d", limit=120)
        if ohlcv is None or ohlcv.empty:
            return []

        snap = compute_momentum(ohlcv)
        if snap is None:
            return []

        option_rows: list[RawOptionRow] | None
        try:
            option_rows = self._option_fetcher(symbol)
        except Exception:
            logger.warning("Option fetch failed for %s", symbol, exc_info=True)
            option_rows = None

        idea = build_idea_from_momentum(
            symbol,
            snap,
            option_rows,
            max_risk_usd=self._max_risk_usd,
        )
        return [idea] if idea is not None else []

    def scan_feed(
        self,
        symbols: Sequence[str] | None = None,
        *,
        watch_only: bool = False,
        min_confidence: float = 0.0,
    ) -> list[EquityOptionsIdea]:
        """Cross-asset Layer 3 feed."""
        universe = tuple(symbols) if symbols is not None else EQUITY_UNIVERSE
        cache_key = f"feed:{','.join(universe)}"

        def _build() -> list[EquityOptionsIdea]:
            return self._scan_many_uncached(universe)

        try:
            ideas = _FEED_CACHE.get_or_set(cache_key, _build)
        except Exception:
            logger.exception("Layer 3 feed scan failed")
            ideas = []

        filtered = [
            idea
            for idea in ideas
            if idea.confidence >= min_confidence
            and (not watch_only or idea.trade_state_hint == "WATCH")
        ]
        filtered.sort(
            key=lambda i: (i.trade_state_hint == "WATCH", i.opportunity_score),
            reverse=True,
        )
        return filtered

    def _scan_many_uncached(self, symbols: Sequence[str]) -> list[EquityOptionsIdea]:
        if not symbols:
            return []
        if len(symbols) == 1:
            return self.scan(symbols[0])

        results: list[EquityOptionsIdea] = []
        workers = min(len(symbols), _FEED_MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self.scan, sym): sym for sym in symbols}
            for future in as_completed(futures):
                try:
                    results.extend(future.result())
                except Exception:
                    logger.exception("Layer 3 scan failed for %s", futures[future])
        return results
