from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from hl_scalper.config import Settings
from hl_scalper.execution import Fill, PaperExecutor
from hl_scalper.feed import BookLevel, L2Book
from hl_scalper.journal import Journal
from hl_scalper.position import PaperPosition, close_at_mid, decide_exit
from hl_scalper.risk import RiskGate
from hl_scalper.sizer import size_notional
from hl_scalper.strategy import StrategyParams, evaluate


@dataclass
class ReplayStats:
    books: int = 0
    signals: int = 0
    fills: int = 0
    exits: int = 0
    pnl_usd: float = 0.0


def book_from_row(row: dict[str, object]) -> L2Book | None:
    coin = str(row.get("coin") or "").upper()
    if not coin:
        return None
    bids_raw = row.get("bids") or []
    asks_raw = row.get("asks") or []
    if not isinstance(bids_raw, list) or not isinstance(asks_raw, list):
        return None
    bids: list[BookLevel] = []
    asks: list[BookLevel] = []
    for item in bids_raw:
        if isinstance(item, dict):
            bids.append(BookLevel(px=float(item["px"]), sz=float(item["sz"])))
    for item in asks_raw:
        if isinstance(item, dict):
            asks.append(BookLevel(px=float(item["px"]), sz=float(item["sz"])))
    if not bids or not asks:
        return None
    return L2Book(coin=coin, bids=bids, asks=asks, age_s=0.0)


def run_replay(
    books_path: Path,
    *,
    settings: Settings,
    out_journal: Path | None = None,
) -> ReplayStats:
    params = StrategyParams(
        imbalance_min=settings.imbalance_min,
        spread_bps_max=settings.spread_bps_max,
        min_notional=settings.min_notional,
        book_levels=settings.book_levels,
    )
    risk = RiskGate(settings)
    executor = PaperExecutor(settings)
    journal = Journal(out_journal) if out_journal else None
    stats = ReplayStats()
    open_pos: PaperPosition | None = None
    latest: dict[str, L2Book] = {}

    if journal:
        journal.write("boot", mode="replay", books_path=str(books_path))

    if not books_path.is_file():
        return stats

    with books_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") != "book":
                continue
            book = book_from_row(row)
            if book is None:
                continue
            stats.books += 1
            latest[book.coin] = book

            if open_pos is not None:
                decision = decide_exit(
                    open_pos,
                    latest.get(open_pos.fill.coin),
                    strategy=params,
                    adverse_bps=settings.adverse_exit_bps,
                )
                if decision.should_exit and decision.reason and decision.exit_mid is not None:
                    closed = close_at_mid(
                        open_pos,
                        decision.exit_mid,
                        exit_fee_bps=settings.taker_fee_bps,
                        reason=decision.reason,
                    )
                    risk.state.open_positions = max(0, risk.state.open_positions - 1)
                    risk.record_pnl(closed.pnl_usd)
                    stats.exits += 1
                    stats.pnl_usd += closed.pnl_usd
                    if journal:
                        journal.write(
                            "exit",
                            fill_id=closed.fill_id,
                            coin=closed.coin,
                            pnl_usd=closed.pnl_usd,
                            reason=closed.reason,
                        )
                    open_pos = None
                continue

            if risk.state.killed:
                continue

            signal = evaluate(book, params)
            if signal is None:
                continue
            stats.signals += 1
            decision = risk.check(signal, book_age_s=0.0)
            if not decision.allowed:
                continue
            sized = size_notional(settings, signal, risk.state.equity_usd)
            if sized.notional_usd <= 0:
                continue
            fill = executor.submit(signal, sized.notional_usd)
            risk.state.open_positions += 1
            open_pos = PaperPosition(
                fill=fill,
                entry_mid=signal.mid,
                opened_at=datetime.now(UTC),
                hold_seconds=settings.hold_seconds,
                entry_imbalance=signal.imbalance,
            )
            stats.fills += 1
            if journal:
                journal.write(
                    "fill",
                    fill_id=fill.fill_id,
                    coin=fill.coin,
                    side=fill.side,
                    px=fill.px,
                    qty=fill.qty,
                    fee_usd=fill.fee_usd,
                )

    # Force flat at end of tape.
    if open_pos is not None:
        book = latest.get(open_pos.fill.coin)
        exit_mid = book.mid if book and book.mid is not None else open_pos.entry_mid
        closed = close_at_mid(
            open_pos,
            exit_mid,
            exit_fee_bps=settings.taker_fee_bps,
            reason="hold_expired",
        )
        stats.exits += 1
        stats.pnl_usd += closed.pnl_usd
        if journal:
            journal.write(
                "exit",
                fill_id=closed.fill_id,
                coin=closed.coin,
                pnl_usd=closed.pnl_usd,
                reason="hold_expired",
            )

    if journal:
        journal.write(
            "replay_done",
            books=stats.books,
            signals=stats.signals,
            fills=stats.fills,
            exits=stats.exits,
            pnl_usd=stats.pnl_usd,
        )
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay recorded HL books through the scalper")
    parser.add_argument("--books", default="data/books.jsonl")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--hold-seconds", type=float, default=None)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    settings = Settings(
        data_dir=str(data_dir),
        journal_path=str(data_dir / "replay_journal.jsonl"),
        hold_seconds=args.hold_seconds if args.hold_seconds is not None else Settings.hold_seconds,
        use_ws=False,
    )
    settings.ensure_data_dirs()
    stats = run_replay(
        Path(args.books),
        settings=settings,
        out_journal=Path(settings.journal_path),
    )
    print(
        f"replay books={stats.books} signals={stats.signals} "
        f"fills={stats.fills} exits={stats.exits} pnl_usd={stats.pnl_usd:.4f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
