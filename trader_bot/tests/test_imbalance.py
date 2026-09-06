from __future__ import annotations

import pytest

from hl_scalper.execution import LiveTradingDisabled, LiveExecutor, PaperExecutor
from hl_scalper.config import Settings
from hl_scalper.feed import BookLevel, L2Book, parse_l2_book
from hl_scalper.risk import RiskGate, RiskState
from hl_scalper.strategy import StrategyParams, evaluate


def _book(*, bid_sz: float, ask_sz: float, spread: float = 0.05) -> L2Book:
    """Default spread 5¢ on $100 mid ≈ 5 bps (under 12 bps cap)."""
    mid = 100.0
    return L2Book(
        coin="BTC",
        bids=[BookLevel(px=mid - spread / 2, sz=bid_sz)],
        asks=[BookLevel(px=mid + spread / 2, sz=ask_sz)],
    )


def test_buy_on_bid_heavy_book() -> None:
    signal = evaluate(_book(bid_sz=900, ask_sz=100), StrategyParams(min_notional=1_000))
    assert signal is not None
    assert signal.side == "buy"
    assert signal.imbalance >= 0.72


def test_sell_on_ask_heavy_book() -> None:
    signal = evaluate(_book(bid_sz=100, ask_sz=900), StrategyParams(min_notional=1_000))
    assert signal is not None
    assert signal.side == "sell"


def test_sit_out_balanced() -> None:
    assert evaluate(_book(bid_sz=500, ask_sz=500), StrategyParams(min_notional=1_000)) is None


def test_sit_out_wide_spread() -> None:
    # 2% spread >> 12 bps
    book = _book(bid_sz=900, ask_sz=100, spread=2.0)
    assert evaluate(book, StrategyParams(min_notional=1_000, spread_bps_max=12.0)) is None


def test_parse_l2_book() -> None:
    payload = {
        "levels": [
            [{"px": "100", "sz": "1"}],
            [{"px": "100.1", "sz": "2"}],
        ]
    }
    book = parse_l2_book("ETH", payload)
    assert book is not None
    assert book.best_bid == 100.0
    assert book.best_ask == 100.1


def test_risk_kills_on_daily_loss() -> None:
    settings = Settings(daily_loss_kill_pct=0.02, paper_equity_usd=10_000)
    gate = RiskGate(settings, RiskState(equity_usd=10_000, day_pnl_usd=-250))
    signal = evaluate(_book(bid_sz=900, ask_sz=100), StrategyParams(min_notional=1_000))
    assert signal is not None
    decision = gate.check(signal, book_age_s=0.1)
    assert not decision.allowed
    assert gate.state.killed


def test_live_executor_always_refuses() -> None:
    settings = Settings(live_enabled=True)
    with pytest.raises(LiveTradingDisabled):
        LiveExecutor(settings).submit(
            evaluate(_book(bid_sz=900, ask_sz=100), StrategyParams(min_notional=1_000)),  # type: ignore[arg-type]
            50.0,
        )


def test_paper_executor_fills() -> None:
    settings = Settings(max_notional_usd=50.0)
    signal = evaluate(_book(bid_sz=900, ask_sz=100), StrategyParams(min_notional=1_000))
    assert signal is not None
    fill = PaperExecutor(settings).submit(signal, 50.0)
    assert fill.status == "paper_fill"
    assert fill.qty > 0
