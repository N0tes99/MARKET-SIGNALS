from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hl_scalper.config import Settings
from hl_scalper.execution import Fill
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.journal import Heartbeat, Journal
from hl_scalper.position import PaperPosition, close_at_mid, mark_pnl
from hl_scalper.sizer import size_notional
from hl_scalper.strategy import Signal, StrategyParams, evaluate


def test_journal_fsync(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    journal = Journal(path)
    journal.write("boot", mode="paper")
    journal.write("signal", coin="BTC", side="buy")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "boot"
    assert json.loads(lines[1])["coin"] == "BTC"


def test_heartbeat(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat.json"
    Heartbeat(path).beat(mode="paper", coins=("BTC",), extra={"ticks": 1})
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["mode"] == "paper"
    assert body["ticks"] == 1


def test_sizer_caps() -> None:
    settings = Settings(max_notional_usd=100.0)
    signal = Signal(
        coin="BTC",
        side="buy",
        imbalance=0.8,
        spread_bps=5.0,
        mid=100.0,
        edge_score=70.0,
        reason="book_imbalance",
    )
    assert size_notional(settings, signal, 10_000.0).notional_usd == 100.0
    assert size_notional(settings, signal, 500.0).notional_usd == 5.0


def test_mark_pnl_long_and_short() -> None:
    assert mark_pnl(
        side="buy",
        qty=1,
        entry_px=100,
        exit_px=101,
        entry_fee_usd=0.1,
        exit_fee_usd=0.1,
    ) == pytest.approx(0.8)
    assert (
        mark_pnl(side="sell", qty=1, entry_px=100, exit_px=99, entry_fee_usd=0, exit_fee_usd=0)
        == 1.0
    )


def test_close_at_mid_hold_expired() -> None:
    fill = Fill(
        fill_id="f1",
        coin="BTC",
        side="buy",
        qty=0.1,
        px=100.0,
        fee_usd=0.05,
        status="paper_fill",
        reason="paper_sim",
        created_at=datetime.now(UTC),
    )
    pos = PaperPosition(
        fill=fill,
        entry_mid=100.0,
        opened_at=datetime.now(UTC) - timedelta(seconds=10),
        hold_seconds=5,
    )
    assert pos.expired()
    closed = close_at_mid(pos, 101.0, exit_fee_bps=3.5)
    assert closed.reason == "hold_expired"
    assert closed.exit_fee_usd > 0


def test_evaluate_still_works_with_tight_book() -> None:
    book = L2Book(
        coin="ETH",
        bids=[BookLevel(px=99.975, sz=900)],
        asks=[BookLevel(px=100.025, sz=100)],
    )
    signal = evaluate(book, StrategyParams(min_notional=1_000))
    assert signal is not None
    assert signal.side == "buy"
