from __future__ import annotations

from datetime import UTC, datetime

from hl_scalper.config import Settings
from hl_scalper.execution.maker import PaperMakerBook, QuoteBook
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.risk import RiskGate
from hl_scalper.strategy.maker import (
    MakerParams,
    evaluate_maker,
    maker_should_cancel,
    maker_should_fill,
    plan_maker_quotes,
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


def test_plan_maker_quotes_flat_twosided() -> None:
    book = _book(100.0, 100.05, bid_sz=500, ask_sz=500)
    p = MakerParams(min_notional=1_000, spread_bps_max=10, twosided=True)
    plan = plan_maker_quotes(book, inventory=None, params=p)
    assert {s.side for s in plan} == {"buy", "sell"}
    assert all(s.execution == "maker" and s.limit_px is not None for s in plan)


def test_plan_maker_quotes_long_asks_only() -> None:
    book = _book(100.0, 100.05, bid_sz=500, ask_sz=500)
    p = MakerParams(min_notional=1_000, spread_bps_max=10, twosided=True)
    plan = plan_maker_quotes(book, inventory="buy", params=p)
    assert len(plan) == 1
    assert plan[0].side == "sell"
    assert plan[0].reason == "maker_flatten_ask"


def test_plan_maker_quotes_short_bids_only() -> None:
    book = _book(100.0, 100.05, bid_sz=500, ask_sz=500)
    p = MakerParams(min_notional=1_000, spread_bps_max=10, twosided=True)
    plan = plan_maker_quotes(book, inventory="sell", params=p)
    assert len(plan) == 1
    assert plan[0].side == "buy"
    assert plan[0].reason == "maker_flatten_bid"


def test_plan_maker_quotes_onesided_lean() -> None:
    book = _book(100.0, 100.05, bid_sz=800, ask_sz=200)
    p = MakerParams(min_notional=1_000, lean=0.55, spread_bps_max=10, twosided=False)
    plan = plan_maker_quotes(book, inventory=None, params=p)
    assert len(plan) == 1
    assert plan[0].side == "buy"


def test_quote_book_keyed_by_coin_side() -> None:
    book = QuoteBook()
    settings = Settings(max_notional_usd=50, maker_fee_bps=1.0, min_notional=1_000)
    engine = PaperMakerBook(settings)
    l2 = _book(100.0, 100.05, bid_sz=500, ask_sz=500)
    plan = plan_maker_quotes(
        l2, inventory=None, params=MakerParams(min_notional=1_000, spread_bps_max=10)
    )
    assert len(plan) == 2
    for sig in plan:
        book.upsert(engine.place(sig, 50.0))
    assert book.sides("BTC") == {"buy", "sell"}
    assert len(book.all_for_coin("BTC")) == 2


def test_risk_allows_reduce_only_while_open() -> None:
    settings = Settings(max_concurrent_positions=1, min_notional=1_000)
    gate = RiskGate(settings)
    gate.state.open_positions = 1
    book = _book(100.0, 100.05, bid_sz=500, ask_sz=500)
    sig = plan_maker_quotes(
        book, inventory="buy", params=MakerParams(min_notional=1_000, spread_bps_max=10)
    )[0]
    blocked = gate.check(sig, book_age_s=0.0)
    assert blocked.allowed is False
    assert blocked.reason == "max_positions"
    ok = gate.check(sig, book_age_s=0.0, reduce_only=True)
    assert ok.allowed is True
