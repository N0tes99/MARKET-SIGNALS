"""Build the crypto perps activity board (Bybit funding + optional Coinglass)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from app.config import settings
from app.engines.opportunity_engine.scanner import SetupScanner
from app.engines.paper_agent.crypto_perp_v2 import V2_UNIVERSE
from app.market_data.providers.bybit_derivatives import (
    fetch_bybit_depth,
    funding_trend,
    oi_change_pct,
)
from app.market_data.providers.coinglass import (
    fetch_aggregated_liquidations,
    score_liquidations,
)
from app.schemas.perps import (
    PerpsBoardSchema,
    PerpsFundingRowSchema,
    PerpsIdeaRowSchema,
    PerpsLiquidationRowSchema,
)
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_BOARD_CACHE: TTLCache[PerpsBoardSchema] = TTLCache(ttl_seconds=90.0)
_BOARD_WORKERS = 6
_COINGLASS_WEB = "https://www.coinglass.com/liquidations"


def _coinglass_url(symbol: str) -> str:
    return f"{_COINGLASS_WEB}/{symbol.upper()}"


def _funding_row(symbol: str) -> PerpsFundingRowSchema:
    try:
        depth = fetch_bybit_depth(symbol)
    except Exception:
        logger.exception("Perps board Bybit depth failed for %s", symbol)
        return PerpsFundingRowSchema(
            symbol=symbol,
            available=False,
            note="Bybit depth failed",
        )

    if depth is None or depth.funding_rate is None:
        return PerpsFundingRowSchema(
            symbol=symbol,
            available=False,
            source=getattr(depth, "source", "") or "",
            note="Funding unavailable",
        )

    funding = float(depth.funding_rate)
    funding_bps = funding * 10_000
    trend = funding_trend(depth.funding_history)
    trend_bps = trend * 10_000 if trend is not None else None
    oi_delta = oi_change_pct(depth.oi_history)
    return PerpsFundingRowSchema(
        symbol=symbol,
        funding_rate=funding,
        funding_bps=round(funding_bps, 3),
        funding_trend_bps=round(trend_bps, 3) if trend_bps is not None else None,
        open_interest=depth.open_interest,
        oi_change_pct=round(oi_delta, 2) if oi_delta is not None else None,
        mark_price=depth.mark_price,
        source=depth.source or "bybit",
        available=True,
        note="",
    )


def _liquidation_row(symbol: str, *, configured: bool) -> PerpsLiquidationRowSchema:
    url = _coinglass_url(symbol)
    if not configured:
        return PerpsLiquidationRowSchema(
            symbol=symbol,
            available=False,
            coinglass_url=url,
            description="Coinglass API key not configured",
        )

    try:
        snap = fetch_aggregated_liquidations(symbol)
    except Exception:
        logger.exception("Perps board liquidations failed for %s", symbol)
        return PerpsLiquidationRowSchema(
            symbol=symbol,
            available=False,
            coinglass_url=url,
            description="Liquidations fetch failed",
        )

    if snap is None:
        return PerpsLiquidationRowSchema(
            symbol=symbol,
            available=False,
            coinglass_url=url,
            description="No liquidation rows",
        )

    score, desc = score_liquidations(snap)
    return PerpsLiquidationRowSchema(
        symbol=symbol,
        long_usd=snap.long_usd,
        short_usd=snap.short_usd,
        total_usd=snap.total_usd,
        long_share=round(snap.long_share, 3),
        interval=snap.interval,
        score=score,
        description=desc,
        available=True,
        coinglass_url=url,
    )


def _idea_rows(scanner: SetupScanner | None) -> list[PerpsIdeaRowSchema]:
    if scanner is None:
        return []
    try:
        ideas = scanner.scan_feed(watch_only=False, min_confidence=55.0)
    except Exception:
        logger.exception("Perps board setups scan failed")
        return []

    keep = {"funding_extreme", "liq_flush", "basis_rich"}
    rows: list[PerpsIdeaRowSchema] = []
    for idea in ideas:
        if idea.setup_type not in keep:
            continue
        rows.append(
            PerpsIdeaRowSchema(
                id=idea.id,
                symbol=idea.symbol,
                setup_type=idea.setup_type,
                direction_bias=idea.direction_bias,
                confidence=float(idea.confidence),
                factors=list(idea.factors[:5]),
                trade_state_hint=str(idea.trade_state_hint),
            )
        )
    rows.sort(key=lambda r: r.confidence, reverse=True)
    return rows[:24]


def build_perps_board(
    *,
    symbols: tuple[str, ...] | None = None,
    setup_scanner: SetupScanner | None = None,
) -> PerpsBoardSchema:
    """Assemble funding + liquidations + Layer-2 perp ideas for the UI."""
    universe = list(symbols or V2_UNIVERSE)
    configured = bool((settings.coinglass_api_key or "").strip())

    def _load() -> PerpsBoardSchema:
        workers = min(_BOARD_WORKERS, max(1, len(universe)))

        def _one(sym: str) -> tuple[PerpsFundingRowSchema, PerpsLiquidationRowSchema]:
            return _funding_row(sym), _liquidation_row(sym, configured=configured)

        if len(universe) <= 1:
            pairs = [_one(universe[0])] if universe else []
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                pairs = list(pool.map(_one, universe))

        funding = [p[0] for p in pairs]
        liquidations = [p[1] for p in pairs]
        funding.sort(
            key=lambda r: abs(r.funding_bps or 0.0),
            reverse=True,
        )
        liquidations.sort(
            key=lambda r: r.total_usd or 0.0,
            reverse=True,
        )

        funding_filled = sum(1 for r in funding if r.available)
        liq_filled = sum(1 for r in liquidations if r.available)
        if not configured:
            liq_note = (
                "Liquidation aggregates need COINGLASS_API_KEY on the API. "
                "Coinglass deep-links stay available; funding board is free via Bybit."
            )
        elif liq_filled == 0:
            liq_note = "Coinglass is configured but no liquidation rows returned this scan."
        else:
            liq_note = f"Coinglass 4h aggregates for {liq_filled}/{len(universe)} names."

        return PerpsBoardSchema(
            as_of=datetime.now(UTC),
            universe=universe,
            funding=funding,
            liquidations=liquidations,
            ideas=_idea_rows(setup_scanner),
            liquidations_configured=configured,
            liquidations_note=liq_note,
            funding_source="bybit",
            symbols_scanned=len(universe),
            funding_filled=funding_filled,
            liquidations_filled=liq_filled,
        )

    cache_key = f"perps:{','.join(universe)}:{int(configured)}"
    return _BOARD_CACHE.get_or_set(cache_key, _load)
