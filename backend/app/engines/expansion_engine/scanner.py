"""Expansion feed scanner — perp v2 universe (16 symbols)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

from app.engines.expansion_engine.compression import analyze_compression
from app.engines.expansion_engine.config import (
    EXPANSION_UNIVERSE,
    ExpansionConfig,
    default_expansion_config,
)
from app.engines.expansion_engine.scoring.composer import compose_scores
from app.engines.expansion_engine.squeeze_fuel import analyze_squeeze_fuel
from app.engines.expansion_engine.state import (
    build_guidance,
    confidence_from_scores,
    resolve_direction_bias,
    resolve_state,
    setup_level_from_compression,
)
from app.engines.expansion_engine.trigger import analyze_trigger
from app.engines.expansion_engine.types import ExpansionCandidate, ExpansionState
from app.market_data.providers.bybit_derivatives import fetch_derivatives_depth
from app.market_data.service import MarketDataService
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_SCAN_CACHE: TTLCache[list[ExpansionCandidate]] = TTLCache(ttl_seconds=60.0)
_SCAN_WORKERS = 6
_MOM_12H_BARS = 12


def _idea_id(symbol: str, state: ExpansionState) -> str:
    return f"{symbol.lower()}-expansion-{state.value}-{uuid4().hex[:8]}"


def _mom_12h_pct(market: MarketDataService, symbol: str) -> float | None:
    df = market.safe_get_ohlcv(symbol, "1h", limit=30)
    if df is None or len(df) < _MOM_12H_BARS + 1:
        return None
    start = float(df["close"].iloc[-(_MOM_12H_BARS + 1)])
    end = float(df["close"].iloc[-1])
    if start <= 0:
        return None
    return (end / start - 1.0) * 100.0


def _spot_price(market: MarketDataService, symbol: str) -> float | None:
    try:
        ticker = market.get_ticker(symbol)
        price = float(ticker.price)
        return price if price > 0 else None
    except Exception:
        return None


class ExpansionScanner:
    """Scans the expansion universe and ranks by net expansion score."""

    def __init__(
        self,
        market_data: MarketDataService | None = None,
        config: ExpansionConfig | None = None,
    ) -> None:
        self._market = market_data or MarketDataService()
        self._config = config or default_expansion_config()

    def scan_symbol(
        self,
        symbol: str,
        *,
        as_of: datetime | None = None,
    ) -> ExpansionCandidate | None:
        """Score one symbol; None when OHLCV unavailable."""
        normalized = symbol.upper()
        cfg = self._config
        now = as_of or datetime.now(UTC)

        df_1h = self._market.safe_get_ohlcv(normalized, "1h", limit=120)
        if df_1h is None:
            return None

        compression = analyze_compression(df_1h, config=cfg)
        mom = _mom_12h_pct(self._market, normalized)
        price = _spot_price(self._market, normalized)
        if price is None and df_1h is not None and not df_1h.empty:
            price = float(df_1h["close"].iloc[-1])

        depth = fetch_derivatives_depth(normalized)
        funding_bps = None
        oi_delta = None
        if depth is not None and depth.funding_rate is not None:
            funding_bps = depth.funding_rate * 10_000
            from app.market_data.providers.bybit_derivatives import oi_change_pct

            oi_delta = oi_change_pct(depth.oi_history)

        squeeze = analyze_squeeze_fuel(
            compression=compression,
            depth=depth,
            price=price,
            recent_momentum_pct=mom,
            config=cfg,
        )

        df_trigger = self._market.safe_get_ohlcv(
            normalized,
            cfg.trigger_timeframe,
            limit=cfg.trigger_volume_lookback + cfg.trigger_range_lookback + 10,
        )
        if df_trigger is not None:
            trigger = analyze_trigger(df_trigger, config=cfg)
        else:
            trigger = analyze_trigger(df_1h, config=cfg)

        state = resolve_state(
            compression=compression,
            squeeze=squeeze,
            trigger=trigger,
            mom_12h_pct=mom,
            config=cfg,
        )

        up, down, contributors, conflicts = compose_scores(
            compression=compression,
            squeeze=squeeze,
            trigger=trigger,
            mom_12h_pct=mom,
            funding_bps=funding_bps,
            state=state,
            config=cfg,
        )
        direction = resolve_direction_bias(up, down, trigger)
        net = up if direction == "up" else down if direction == "down" else max(up, down)
        horizon, invalidation, key_trigger = build_guidance(
            state=state,
            direction=direction,
            trigger=trigger,
        )

        factors: list[str] = []
        if compression:
            factors.extend(compression.factors[:3])
        factors.extend(squeeze.factors[:2])
        factors.extend(trigger.factors[:2])

        comp_result = compression or analyze_compression(df_1h, config=cfg)
        if comp_result is None:
            from app.engines.expansion_engine.types import CompressionResult

            comp_result = CompressionResult(
                score=50.0,
                atr_percentile=None,
                bb_width_percentile=None,
                range_compression_pct=None,
                volume_compression_pct=None,
                factors=["Compression data insufficient"],
            )

        conf: str = confidence_from_scores(net, trigger.active)
        setup: str = setup_level_from_compression(compression)

        return ExpansionCandidate(
            id=_idea_id(normalized, state),
            symbol=normalized,
            state=state,
            direction_bias=direction,
            up_score=up,
            down_score=down,
            net_score=net,
            confidence=conf,  # type: ignore[arg-type]
            setup_level=setup,  # type: ignore[arg-type]
            trigger_active=trigger.active,
            horizon=horizon,
            invalidation=invalidation,
            key_trigger=key_trigger,
            compression=comp_result,
            squeeze=squeeze,
            trigger=trigger,
            contributors=contributors,
            conflicts=conflicts,
            factors=factors,
            price=price,
            funding_bps=round(funding_bps, 2) if funding_bps is not None else None,
            oi_change_pct=round(oi_delta, 2) if oi_delta is not None else None,
            mom_12h_pct=round(mom, 2) if mom is not None else None,
            as_of=now,
        )

    def scan(
        self,
        *,
        symbols: tuple[str, ...] | None = None,
        use_cache: bool = True,
    ) -> list[ExpansionCandidate]:
        """Scan universe; highest net score first."""
        universe = symbols or self._config.universe
        cache_key = ",".join(universe)
        if use_cache:
            cached = _SCAN_CACHE.get(cache_key)
            if cached is not None:
                return cached

        results: list[ExpansionCandidate] = []

        def _one(sym: str) -> ExpansionCandidate | None:
            try:
                return self.scan_symbol(sym)
            except Exception:
                logger.exception("expansion scan failed for %s", sym)
                return None

        workers = min(_SCAN_WORKERS, max(1, len(universe)))
        if len(universe) <= 1:
            raw = [_one(universe[0])] if universe else []
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                raw = list(pool.map(_one, universe))

        for item in raw:
            if item is not None:
                results.append(item)

        results.sort(key=lambda c: c.net_score, reverse=True)
        if use_cache:
            _SCAN_CACHE.set(cache_key, results)
        return results


def scan_expansion_feed(
    market: MarketDataService | None = None,
    *,
    symbols: tuple[str, ...] | None = None,
    use_cache: bool = True,
) -> list[ExpansionCandidate]:
    """Convenience wrapper for API routes."""
    scanner = ExpansionScanner(market_data=market, config=default_expansion_config())
    return scanner.scan(symbols=symbols or EXPANSION_UNIVERSE, use_cache=use_cache)
