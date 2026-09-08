"""Paper resting post-only quotes (S2 maker scaffold)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from hl_scalper.config import Settings
from hl_scalper.feed import L2Book
from hl_scalper.sim import taker_fee_usd
from hl_scalper.strategy import Side, Signal
from hl_scalper.strategy.maker import maker_should_cancel, maker_should_fill
from hl_scalper.types import Fill


@dataclass
class RestingQuote:
    coin: str
    side: Side
    limit_px: float
    qty: float
    notional_usd: float
    placed_mid: float
    placed_at: datetime
    reason: str
    cloid: str
    imbalance: float
    spread_bps: float
    edge_score: float


class PaperMakerBook:
    """One resting post-only order; cancel / fill from L2 touch."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def place(self, signal: Signal, notional_usd: float) -> RestingQuote:
        if signal.execution != "maker" or signal.limit_px is None:
            raise ValueError("maker signal required")
        size = min(notional_usd, self.settings.max_notional_usd)
        px = float(signal.limit_px)
        qty = size / px if px > 0 else 0.0
        if qty <= 0:
            raise ValueError("dust maker qty")
        return RestingQuote(
            coin=signal.coin,
            side=signal.side,
            limit_px=px,
            qty=qty,
            notional_usd=size,
            placed_mid=signal.mid,
            placed_at=datetime.now(UTC),
            reason=signal.reason,
            cloid=str(uuid4()),
            imbalance=signal.imbalance,
            spread_bps=signal.spread_bps,
            edge_score=signal.edge_score,
        )

    def poll(
        self, quote: RestingQuote, book: L2Book | None
    ) -> tuple[str, Fill | None, str]:
        """Return (rest|fill|cancel, fill?, reason)."""
        if book is None:
            return "cancel", None, "no_book"
        cancel, why = maker_should_cancel(
            side=quote.side,
            limit_px=quote.limit_px,
            placed_mid=quote.placed_mid,
            book=book,
            cancel_bps=self.settings.maker_cancel_bps,
        )
        if cancel:
            return "cancel", None, why
        if maker_should_fill(side=quote.side, limit_px=quote.limit_px, book=book):
            fee = taker_fee_usd(quote.qty * quote.limit_px, self.settings.maker_fee_bps)
            fill = Fill(
                fill_id=quote.cloid,
                coin=quote.coin,
                side=quote.side,
                qty=quote.qty,
                px=quote.limit_px,
                fee_usd=fee,
                status="paper_maker_fill",
                reason="maker_touch",
                created_at=datetime.now(UTC),
            )
            return "fill", fill, "maker_touch"
        return "rest", None, "resting"
