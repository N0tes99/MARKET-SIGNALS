from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from hl_scalper.arming import check_arming
from hl_scalper.execution import Fill
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.position import PaperPosition, decide_exit
from hl_scalper.reconcile import VenuePosition, VenueState, parse_clearinghouse, reconcile_flat_local
from hl_scalper.report import analyze_journal
from hl_scalper.strategy import StrategyParams


def _pos(side: str = "buy") -> PaperPosition:
    fill = Fill(
        fill_id="f1",
        coin="BTC",
        side=side,
        qty=0.1,
        px=100.0,
        fee_usd=0.05,
        status="paper_fill",
        reason="paper_sim",
        created_at=datetime.now(UTC),
    )
    return PaperPosition(
        fill=fill,
        entry_mid=100.0,
        opened_at=datetime.now(UTC) - timedelta(seconds=2),
        hold_seconds=30,
        entry_imbalance=0.8,
    )


def _book(bid_sz: float, ask_sz: float, mid: float = 100.0, spread: float = 0.05) -> L2Book:
    return L2Book(
        coin="BTC",
        bids=[BookLevel(px=mid - spread / 2, sz=bid_sz)],
        asks=[BookLevel(px=mid + spread / 2, sz=ask_sz)],
    )


def test_exit_adverse_mid() -> None:
    pos = _pos("buy")
    book = _book(900, 100, mid=99.8)  # mid dropped ~20 bps
    decision = decide_exit(pos, book, strategy=StrategyParams(min_notional=1_000), adverse_bps=8.0)
    assert decision.should_exit
    assert decision.reason == "adverse_mid"


def test_exit_imbalance_flip() -> None:
    pos = _pos("buy")
    # Ask-heavy → sell signal / flip
    book = _book(100, 900, mid=100.0)
    decision = decide_exit(pos, book, strategy=StrategyParams(min_notional=1_000), adverse_bps=50.0)
    assert decision.should_exit
    assert decision.reason == "imbalance_flip"


def test_arming_requires_all_gates(tmp_path: Path, monkeypatch) -> None:
    arm = tmp_path / "ARMED"
    status = check_arming(
        live_enabled=True,
        allow_live_orders=True,
        arm_file=arm,
        killed=False,
    )
    assert not status.ok
    assert "missing_arm_file" in status.reasons

    arm.write_text("ok\n", encoding="utf-8")
    monkeypatch.setenv("HL_AGENT_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("HL_MASTER_ADDRESS", "0xmaster")
    monkeypatch.delenv("HL_MASTER_PRIVATE_KEY", raising=False)
    status = check_arming(
        live_enabled=True,
        allow_live_orders=True,
        arm_file=arm,
        killed=False,
    )
    assert status.ok


def test_arming_refuses_master_private_key(tmp_path: Path, monkeypatch) -> None:
    arm = tmp_path / "ARMED"
    arm.write_text("ok\n", encoding="utf-8")
    monkeypatch.setenv("HL_AGENT_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("HL_MASTER_ADDRESS", "0xmaster")
    monkeypatch.setenv("HL_MASTER_PRIVATE_KEY", "0xbad")
    status = check_arming(
        live_enabled=True,
        allow_live_orders=True,
        arm_file=arm,
        killed=False,
    )
    assert not status.ok
    assert "master_private_key_present_refuse" in status.reasons


def test_reconcile_flat_ok() -> None:
    venue = VenueState("0x1", 100.0, 0.0, ())
    assert reconcile_flat_local(local_open_coin=None, venue=venue).ok


def test_reconcile_flags_venue_positions() -> None:
    venue = VenueState(
        "0x1",
        100.0,
        50.0,
        (VenuePosition("BTC", 0.01, 100.0, 1.0),),
    )
    result = reconcile_flat_local(local_open_coin=None, venue=venue)
    assert not result.ok


def test_parse_clearinghouse_empty() -> None:
    state = parse_clearinghouse("0x1", {"marginSummary": {"accountValue": "10"}, "assetPositions": []})
    assert state.account_value == 10.0
    assert state.positions == ()


def test_report_expectancy(tmp_path: Path) -> None:
    path = tmp_path / "journal.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"event":"signal"}',
                '{"event":"fill","fee_usd":0.1}',
                '{"event":"exit","pnl_usd":1.5,"entry_fee_usd":0.1,"exit_fee_usd":0.1,"reason":"adverse_mid"}',
                '{"event":"exit","pnl_usd":-0.5,"entry_fee_usd":0.1,"exit_fee_usd":0.1,"reason":"hold_expired"}',
                '{"event":"sit_out"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    report = analyze_journal(path)
    assert report.exits == 2
    assert report.expectancy == 0.5
    assert report.wins == 1
    assert report.losses == 1
