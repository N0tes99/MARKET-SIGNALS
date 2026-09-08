from __future__ import annotations

from datetime import UTC, datetime

from hl_scalper.config import Settings
from hl_scalper.execution.maker import PaperMakerBook
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.risk import RiskGate
from hl_scalper.strategy.maker import (
    MakerParams,
    evaluate_maker,
    maker_should_cancel,
    maker_should_fill,
    post_only_limit,
)


def _book(bid: float, ask: float, bid_sz: float = 900, ask_sz: float = 100) -> L2Book:
    return L2Book(
        coin="BTC",
        bids=[BookLevel(px=bid, sz=bid_sz)],
        asks=[BookLevel(px=ask, sz=ask_sz)],
    )


def test_post_only_limit_does_not_cross() -> None:
    book = _book(100.0, 100.1)
    buy = post_only_limit(book, "buy")
    sell = post_only_limit(book, "sell")
    assert buy is not None and buy < 100.1
    assert sell is not None and sell > 100.0
    assert buy == 100.0
    assert sell == 100.1


def test_evaluate_maker_bid_lean() -> None:
    book = _book(100.0, 100.05, bid_sz=800, ask_sz=200)
    sig = evaluate_maker(book, MakerParams(min_notional=1_000, lean=0.55, spread_bps_max=10))
    assert sig is not None
    assert sig.execution == "maker"
    assert sig.side == "buy"
    assert sig.limit_px == 100.0


def test_maker_cancel_adverse() -> None:
    book = _book(100.0, 100.1)
    cancel, why = maker_should_cancel(
        side="buy",
        limit_px=100.0,
        placed_mid=100.05,
        book=_book(100.2, 100.3),  # mid rose
        cancel_bps=4.0,
    )
    assert cancel is True
    assert why == "adverse_mid"


def test_maker_fill_on_sell_pressure() -> None:
    # Join bid; mid at/below midpoint → fill
    book = _book(100.0, 100.02, bid_sz=500, ask_sz=500)
    assert maker_should_fill(side="buy", limit_px=100.0, book=book) is True


def test_paper_maker_place_and_fill() -> None:
    settings = Settings(max_notional_usd=50, maker_fee_bps=1.0, maker_cancel_bps=4.0, min_notional=1_000)
    engine = PaperMakerBook(settings)
    book = _book(100.0, 100.05, bid_sz=800, ask_sz=200)
    sig = evaluate_maker(book, MakerParams(min_notional=1_000, lean=0.55))
    assert sig is not None
    gate = RiskGate(settings).check(sig, book_age_s=0.0)
    assert gate.allowed, gate.reason
    quote = engine.place(sig, 50.0)
    assert quote.limit_px == 100.0
    fill_book = _book(100.0, 100.02, bid_sz=500, ask_sz=500)
    outcome2, fill2, why = engine.poll(quote, fill_book)
    assert outcome2 == "fill"
    assert fill2 is not None
    assert fill2.status == "paper_maker_fill"
    assert fill2.fee_usd > 0
    assert why == "maker_touch"
