"""Alpaca read-only mirror + free-tier IEX activity endpoints."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query

from app.adapters.brokers.alpaca import AlpacaMirrorSnapshot, fetch_alpaca_mirror
from app.adapters.brokers.alpaca_market_data import (
    AlpacaActivitySnapshot,
    fetch_alpaca_activity,
)
from app.schemas.alpaca import (
    AlpacaAccountSchema,
    AlpacaActivityRowSchema,
    AlpacaActivitySchema,
    AlpacaFillSchema,
    AlpacaMirrorSchema,
    AlpacaPositionSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _mirror_schema(snap: AlpacaMirrorSnapshot) -> AlpacaMirrorSchema:
    account = None
    if snap.account is not None:
        account = AlpacaAccountSchema(
            equity=snap.account.equity,
            cash=snap.account.cash,
            buying_power=snap.account.buying_power,
            portfolio_value=snap.account.portfolio_value,
            status=snap.account.status,
            currency=snap.account.currency,
        )
    return AlpacaMirrorSchema(
        configured=snap.configured,
        mode=snap.mode,
        base_url=snap.base_url,
        as_of=snap.as_of,
        cached=snap.cached,
        error=snap.error,
        account=account,
        positions=[
            AlpacaPositionSchema(
                symbol=p.symbol,
                qty=p.qty,
                side=p.side,
                market_value=p.market_value,
                cost_basis=p.cost_basis,
                unrealized_pl=p.unrealized_pl,
                unrealized_plpc=p.unrealized_plpc,
                current_price=p.current_price,
                avg_entry_price=p.avg_entry_price,
                change_today=p.change_today,
            )
            for p in snap.positions
        ],
        recent_fills=[
            AlpacaFillSchema(
                id=f.id,
                symbol=f.symbol,
                side=f.side,
                qty=f.qty,
                filled_avg_price=f.filled_avg_price,
                filled_at=f.filled_at,
                status=f.status,
                order_type=f.order_type,
                notional=f.notional,
            )
            for f in snap.recent_fills
        ],
    )


def _activity_schema(snap: AlpacaActivitySnapshot) -> AlpacaActivitySchema:
    return AlpacaActivitySchema(
        configured=snap.configured,
        feed=snap.feed,
        data_base_url=snap.data_base_url,
        as_of=snap.as_of,
        cached=snap.cached,
        error=snap.error,
        symbols_requested=list(snap.symbols_requested),
        rows=[
            AlpacaActivityRowSchema(
                symbol=r.symbol,
                last_price=r.last_price,
                daily_volume=r.daily_volume,
                change_pct=r.change_pct,
                daily_bar_close=r.daily_bar_close,
                prev_close=r.prev_close,
                trade_time=r.trade_time,
            )
            for r in snap.rows
        ],
    )


@router.get("/mirror", response_model=AlpacaMirrorSchema)
async def alpaca_mirror() -> AlpacaMirrorSchema:
    """Mirror Alpaca positions + recent fills (read-only, short TTL cache).

    Returns ``configured=false`` when API keys are missing — no error.
    Never places or cancels orders.
    """
    snap = await asyncio.to_thread(fetch_alpaca_mirror)
    return _mirror_schema(snap)


@router.get("/activity", response_model=AlpacaActivitySchema)
async def alpaca_activity(
    symbols: str | None = Query(
        default=None,
        description=(
            "Comma-separated equity/ETF symbols. "
            "Omit to scan tracked stocks+ETFs (crypto excluded). "
            "Always uses free IEX feed — never SIP."
        ),
    ),
) -> AlpacaActivitySchema:
    """Free-tier Alpaca IEX stock snapshots (last/change/volume).

    Soft-fails when market data is unavailable. Does not affect ranking.
    Yahoo remains the primary OHLCV source.
    """
    parsed: list[str] | None = None
    if symbols and symbols.strip():
        parsed = [part.strip() for part in symbols.split(",") if part.strip()]
    snap = await asyncio.to_thread(fetch_alpaca_activity, parsed)
    return _activity_schema(snap)
