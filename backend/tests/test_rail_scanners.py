"""Hyperliquid-native Rail scanners — mocked /info, no live orders."""

from __future__ import annotations

from app.engines.rail.adapters.hyperliquid_info import (
    HL_PERP_UNIVERSE,
    BookLevel,
    L2Book,
    OutcomeSpec,
    PerpContext,
    _parse_l2_book,
    _parse_outcomes,
    _parse_perp_contexts,
)
from app.engines.rail.desk import RailDesk
from app.engines.rail.envelope import assert_clerk_payload_is_blind
from app.engines.rail.scanners import HyperliquidRailScanner
from app.engines.rail.scanners.book import scan_books
from app.engines.rail.scanners.funding import scan_funding
from app.engines.rail.scanners.outcome import scan_outcomes
from app.market_data.perp_universe import PERP_V2_UNIVERSE


class FakeInfo:
    def __init__(
        self,
        *,
        ctxs: list[PerpContext] | None = None,
        books: dict[str, L2Book] | None = None,
        outcomes: list[OutcomeSpec] | None = None,
    ) -> None:
        self._ctxs = ctxs or []
        self._books = books or {}
        self._outcomes = outcomes or []

    def perp_contexts(self, coins: tuple[str, ...] = ()) -> list[PerpContext]:
        wanted = {coin.upper() for coin in coins} if coins else None
        if wanted is None:
            return list(self._ctxs)
        return [row for row in self._ctxs if row.coin in wanted]

    def l2_book(self, coin: str) -> L2Book | None:
        return self._books.get(coin)

    def outcomes(self, limit: int = 3) -> list[OutcomeSpec]:
        return list(self._outcomes)[:limit]


def _stacked_bids(coin: str = "HYPE") -> L2Book:
    return L2Book(
        coin=coin,
        bids=[BookLevel(px=10.0, sz=8_000.0) for _ in range(5)],
        asks=[BookLevel(px=10.01, sz=40.0) for _ in range(5)],
    )


def test_parse_perp_contexts_keeps_hype() -> None:
    payload = [
        {"universe": [{"name": "BTC"}, {"name": "HYPE"}]},
        [
            {"funding": "0.00001", "premium": "0.0", "markPx": "100"},
            {"funding": "0.0004", "premium": "0.0002", "markPx": "20"},
        ],
    ]
    rows = _parse_perp_contexts(payload, {"HYPE"})
    assert len(rows) == 1
    assert rows[0].coin == "HYPE"
    assert rows[0].funding == 0.0004


def test_hl_universe_includes_hype_which_se_does_not_scan() -> None:
    assert "HYPE" in HL_PERP_UNIVERSE
    assert "HYPE" not in PERP_V2_UNIVERSE


def test_parse_l2_book_requires_both_sides() -> None:
    assert _parse_l2_book("HYPE", {"levels": [[{"px": "10", "sz": "1"}]]}) is None
    book = _parse_l2_book(
        "HYPE",
        {
            "levels": [
                [{"px": "10", "sz": "2"}],
                [{"px": "10.01", "sz": "1"}],
            ]
        },
    )
    assert book is not None
    assert book.best_bid == 10.0
    assert book.best_ask == 10.01


def test_parse_outcomes_from_wrapped_payload() -> None:
    rows = _parse_outcomes(
        {
            "outcomes": [
                {
                    "outcome": 7,
                    "name": "Daily",
                    "description": "class:priceBinary|underlying:BTC|expiry:20260821",
                }
            ]
        }
    )
    assert rows[0].outcome_id == 7


def test_book_scanner_buys_bid_stack_on_hype() -> None:
    info = FakeInfo(books={"HYPE": _stacked_bids(), "BTC": _stacked_bids("BTC")})
    pairs = scan_books(info)
    assert pairs
    envelope, sealed = pairs[0]
    assert sealed.symbol == "HYPE" or sealed.symbol == "BTC"
    assert envelope.side == "buy"
    assert envelope.invalidation == "book_imbalance"
    assert envelope.market_kind == "perp"
    assert_clerk_payload_is_blind(
        envelope.clerk_dict(), banned_symbols=("HYPE", "BTC", "ETH", "SOL")
    )


def test_funding_scanner_requires_hl_premium_agreement() -> None:
    disagree = PerpContext(
        coin="HYPE",
        funding=0.0004,
        premium=-0.0002,
        mark_px=20.0,
        oracle_px=20.0,
        open_interest=1.0,
        mid_px=20.0,
    )
    agree = PerpContext(
        coin="HYPE",
        funding=0.0004,
        premium=0.0002,
        mark_px=20.0,
        oracle_px=20.0,
        open_interest=1.0,
        mid_px=20.0,
    )
    assert scan_funding(FakeInfo(ctxs=[disagree])) == []
    pairs = scan_funding(FakeInfo(ctxs=[agree]))
    assert len(pairs) == 1
    envelope, sealed = pairs[0]
    assert sealed.symbol == "HYPE"
    assert envelope.side == "sell"
    assert envelope.invalidation == "hl_funding"
    assert_clerk_payload_is_blind(envelope.clerk_dict(), banned_symbols=("HYPE", "BTC"))


def test_outcome_scanner_is_blind_to_underlying() -> None:
    spec = OutcomeSpec(
        outcome_id=3,
        name="Daily",
        description="class:priceBinary|underlying:BTC|expiry:20260821-0800",
    )
    books = {
        "#30": L2Book(
            coin="#30",
            bids=[BookLevel(0.39, 500.0)],
            asks=[BookLevel(0.41, 500.0)],
        ),
        "#31": L2Book(
            coin="#31",
            bids=[BookLevel(0.39, 500.0)],
            asks=[BookLevel(0.41, 500.0)],
        ),
    }
    pairs = scan_outcomes(FakeInfo(outcomes=[spec], books=books))
    assert len(pairs) == 1
    envelope, sealed = pairs[0]
    assert envelope.market_kind == "outcome"
    assert envelope.invalidation == "outcome_gap"
    assert "BTC" not in sealed.symbol
    assert_clerk_payload_is_blind(
        envelope.clerk_dict(), banned_symbols=("BTC", "ETH", "HYPE")
    )
    blob = str(envelope.clerk_dict())
    assert "Daily" not in blob
    assert "priceBinary" not in blob


def test_desk_snapshot_phase_b_from_hype_only() -> None:
    info = FakeInfo(
        ctxs=[
            PerpContext(
                coin="HYPE",
                funding=0.0004,
                premium=0.0002,
                mark_px=20.0,
                oracle_px=20.0,
                open_interest=1.0,
                mid_px=20.0,
            )
        ],
        books={"HYPE": _stacked_bids()},
    )
    desk = RailDesk(scanner=HyperliquidRailScanner(info=info))
    snap = desk.snapshot()
    assert snap.phase == "B"
    assert "phase_b_hl_scanners" in snap.notes
    assert snap.sitting_out is False
    for item in snap.envelopes:
        assert_clerk_payload_is_blind(
            item.clerk_dict(), banned_symbols=("HYPE", "BTC", "ETH", "SOL")
        )
    envelope, fill = desk.simulate(snap.envelopes[0].envelope_id)
    assert fill is not None
    assert fill.status == "paper_ack"
    assert envelope is not None


def test_desk_sits_out_when_scan_is_empty() -> None:
    desk = RailDesk(scanner=HyperliquidRailScanner(info=FakeInfo()))
    snap = desk.snapshot()
    assert snap.sitting_out is True
    assert snap.envelopes == []
    assert "sitting_out" in snap.notes
    assert snap.phase == "B"
