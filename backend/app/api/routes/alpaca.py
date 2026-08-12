"""Alpaca read-only mirror endpoints (no order execution)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter

from app.adapters.brokers.alpaca import AlpacaMirrorSnapshot, fetch_alpaca_mirror
from app.schemas.alpaca import (
    AlpacaAccountSchema,
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


@router.get("/mirror", response_model=AlpacaMirrorSchema)
async def alpaca_mirror() -> AlpacaMirrorSchema:
    """Mirror Alpaca positions + recent fills (read-only, short TTL cache).

    Returns ``configured=false`` when API keys are missing — no error.
    Never places or cancels orders.
    """
    snap = await asyncio.to_thread(fetch_alpaca_mirror)
    return _mirror_schema(snap)
