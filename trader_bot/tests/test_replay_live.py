from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from eth_account import Account

from hl_scalper.config import Settings
from hl_scalper.exchange import HlExchangeClient
from hl_scalper.execution import LiveExecutor, LiveTradingDisabled, PaperExecutor
from hl_scalper.position import PaperPosition
from hl_scalper.replay import book_from_row, run_replay
from hl_scalper.strategy import Signal


def test_replay_from_recorded_books(tmp_path: Path) -> None:
    books = tmp_path / "books.jsonl"
    # Bid-heavy then ask-heavy to force entry + flip exit.
    rows = [
        {
            "event": "book",
            "coin": "BTC",
            "bids": [{"px": 99.975, "sz": 900}],
            "asks": [{"px": 100.025, "sz": 100}],
        },
        {
            "event": "book",
            "coin": "BTC",
            "bids": [{"px": 99.975, "sz": 100}],
            "asks": [{"px": 100.025, "sz": 900}],
        },
        {
            "event": "book",
            "coin": "BTC",
            "bids": [{"px": 99.975, "sz": 100}],
            "asks": [{"px": 100.025, "sz": 900}],
        },
    ]
    books.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    settings = Settings(
        min_notional=1_000,
        hold_seconds=0,
        adverse_exit_bps=50,
        data_dir=str(tmp_path),
        journal_path=str(tmp_path / "replay_journal.jsonl"),
        max_notional_usd=50,
        paper_equity_usd=10_000,
        spread_bps_max=20.0,
        fee_edge_buffer_bps=0.0,
    )
    stats = run_replay(books, settings=settings, out_journal=Path(settings.journal_path))
    assert stats.books == 3
    assert stats.fills >= 1
    assert stats.exits >= 1


def test_book_from_row() -> None:
    book = book_from_row(
        {
            "coin": "ETH",
            "bids": [{"px": 1, "sz": 2}],
            "asks": [{"px": 1.1, "sz": 2}],
        }
    )
    assert book is not None
    assert book.coin == "ETH"
    assert book.best_bid == 1.0


def test_live_dry_run_submit(tmp_path: Path, monkeypatch) -> None:
    arm = tmp_path / "ARMED"
    arm.write_text("1\n", encoding="utf-8")
    # Deterministic throwaway key — never used on mainnet in this test (dry_run).
    acct = Account.create()
    monkeypatch.setenv("HL_AGENT_PRIVATE_KEY", acct.key.hex())
    monkeypatch.setenv("HL_MASTER_ADDRESS", "0x" + "11" * 20)
    monkeypatch.delenv("HL_MASTER_PRIVATE_KEY", raising=False)

    settings = Settings(
        live_enabled=True,
        allow_live_orders=True,
        dry_run_live=True,
        arm_file=str(arm),
        live_coins=("BTC",),
        max_notional_usd=25,
    )
    client = HlExchangeClient(
        agent_private_key=acct.key.hex(),
        master_address="0x" + "11" * 20,
        dry_run=True,
    )
    ex = LiveExecutor(settings, client=client)
    signal = Signal(
        coin="BTC",
        side="buy",
        imbalance=0.8,
        spread_bps=2.0,
        mid=100.0,
        edge_score=70.0,
        reason="book_imbalance",
    )
    fill = ex.submit(signal, 25.0)
    assert fill.status == "dry_run_fill"
    assert fill.qty > 0

    pos = PaperPosition(
        fill=fill,
        entry_mid=100.0,
        opened_at=datetime.now(UTC),
        hold_seconds=5,
    )
    close = ex.close_position(pos, 100.0)
    assert close.status == "dry_run_fill"


def test_live_refuses_without_arm(tmp_path: Path) -> None:
    settings = Settings(
        live_enabled=True,
        allow_live_orders=True,
        dry_run_live=True,
        arm_file=str(tmp_path / "missing"),
    )
    ex = LiveExecutor(settings)
    signal = Signal(
        coin="BTC",
        side="buy",
        imbalance=0.8,
        spread_bps=2.0,
        mid=100.0,
        edge_score=70.0,
        reason="book_imbalance",
    )
    try:
        ex.submit(signal, 10.0)
        assert False, "expected LiveTradingDisabled"
    except LiveTradingDisabled as exc:
        assert "not armed" in str(exc)


def test_paper_close_position() -> None:
    settings = Settings(max_notional_usd=50)
    ex = PaperExecutor(settings)
    signal = Signal(
        coin="BTC",
        side="buy",
        imbalance=0.8,
        spread_bps=2.0,
        mid=100.0,
        edge_score=70.0,
        reason="book_imbalance",
    )
    fill = ex.submit(signal, 50)
    pos = PaperPosition(fill=fill, entry_mid=100.0, opened_at=datetime.now(UTC), hold_seconds=1)
    close = ex.close_position(pos, 101.0)
    assert close.side == "sell"
    assert close.px == 101.0
