from __future__ import annotations

import argparse
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from hl_scalper.config import Settings
from hl_scalper.execution import LiveTradingDisabled, build_executor
from hl_scalper.feed import HttpInfoFeed, L2Book
from hl_scalper.journal import Heartbeat, Journal
from hl_scalper.position import PaperPosition, close_at_mid
from hl_scalper.risk import RiskGate
from hl_scalper.sizer import size_notional
from hl_scalper.strategy import StrategyParams, evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HL book-imbalance scalper lab")
    parser.add_argument("--mode", choices=("paper", "live"), default="paper")
    parser.add_argument("--coins", default="BTC,ETH,SOL,HYPE")
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    parser.add_argument("--interval", type=float, default=None)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--hold-seconds", type=float, default=None)
    parser.add_argument("--record-books", action="store_true")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    settings = Settings(
        coins=tuple(c.strip().upper() for c in args.coins.split(",") if c.strip()),
        poll_interval_s=args.interval if args.interval is not None else Settings.poll_interval_s,
        hold_seconds=args.hold_seconds if args.hold_seconds is not None else Settings.hold_seconds,
        data_dir=str(data_dir),
        journal_path=str(data_dir / "journal.jsonl"),
        heartbeat_path=str(data_dir / "heartbeat.json"),
        books_path=str(data_dir / "books.jsonl"),
        record_books=bool(args.record_books),
    )
    if args.mode == "live" and not settings.live_enabled:
        print("live mode refused: settings.live_enabled is False", file=sys.stderr)
        return 2

    settings.ensure_data_dirs()
    journal = Journal(Path(settings.journal_path))
    heartbeat = Heartbeat(Path(settings.heartbeat_path))
    books_journal = Journal(Path(settings.books_path)) if settings.record_books else None

    feed = HttpInfoFeed(base_url=settings.info_url)
    risk = RiskGate(settings)
    executor = build_executor(settings, mode=args.mode)
    params = StrategyParams(
        imbalance_min=settings.imbalance_min,
        spread_bps_max=settings.spread_bps_max,
        min_notional=settings.min_notional,
        book_levels=settings.book_levels,
    )
    open_pos: PaperPosition | None = None
    feed_failures = 0
    ticks = 0

    journal.write(
        "boot",
        mode=args.mode,
        coins=list(settings.coins),
        hold_seconds=settings.hold_seconds,
        equity_usd=settings.paper_equity_usd,
    )

    def manage_exit(books: dict[str, L2Book]) -> None:
        nonlocal open_pos
        if open_pos is None or not open_pos.expired():
            return
        book = books.get(open_pos.fill.coin)
        exit_mid = book.mid if book and book.mid is not None else open_pos.entry_mid
        closed = close_at_mid(
            open_pos,
            exit_mid,
            exit_fee_bps=settings.taker_fee_bps,
            reason="hold_expired",
        )
        risk.state.open_positions = max(0, risk.state.open_positions - 1)
        risk.record_pnl(closed.pnl_usd)
        journal.write(
            "exit",
            fill_id=closed.fill_id,
            coin=closed.coin,
            side=closed.side,
            qty=closed.qty,
            entry_px=closed.entry_px,
            exit_px=closed.exit_px,
            entry_fee_usd=closed.entry_fee_usd,
            exit_fee_usd=closed.exit_fee_usd,
            pnl_usd=closed.pnl_usd,
            hold_seconds=closed.hold_seconds,
            reason=closed.reason,
            day_pnl_usd=risk.state.day_pnl_usd,
            killed=risk.state.killed,
        )
        open_pos = None

    def tick() -> None:
        nonlocal open_pos, feed_failures, ticks
        ticks += 1
        books: dict[str, L2Book] = {}
        got_any = False
        for coin in settings.coins:
            try:
                book = feed.l2_book(coin)
            except Exception as exc:  # noqa: BLE001 — daemon must stay up
                feed_failures += 1
                journal.write(
                    "feed_error",
                    coin=coin,
                    error=str(exc),
                    feed_failures=feed_failures,
                )
                if feed_failures >= settings.max_feed_failures:
                    risk.trip(f"feed_failures:{feed_failures}")
                    journal.write("kill", reason=risk.state.kill_reason)
                continue
            if book is None:
                journal.write("sit_out", coin=coin, reason="no_book")
                continue
            got_any = True
            books[coin] = book
            if books_journal is not None:
                books_journal.write(
                    "book",
                    coin=coin,
                    bids=[{"px": lvl.px, "sz": lvl.sz} for lvl in book.bids[: settings.book_levels]],
                    asks=[{"px": lvl.px, "sz": lvl.sz} for lvl in book.asks[: settings.book_levels]],
                )

        if got_any:
            feed_failures = 0

        manage_exit(books)

        if open_pos is not None or risk.state.killed:
            heartbeat.beat(
                mode=args.mode,
                coins=settings.coins,
                extra={
                    "ticks": ticks,
                    "open": open_pos.fill.coin if open_pos else None,
                    "day_pnl_usd": risk.state.day_pnl_usd,
                    "killed": risk.state.killed,
                },
            )
            return

        for coin, book in books.items():
            signal = evaluate(book, params)
            if signal is None:
                journal.write("sit_out", coin=coin, reason="no_signal")
                continue
            journal.write(
                "signal",
                coin=signal.coin,
                side=signal.side,
                imbalance=signal.imbalance,
                spread_bps=signal.spread_bps,
                mid=signal.mid,
                edge_score=signal.edge_score,
            )
            decision = risk.check(signal, book_age_s=book.age_s)
            if not decision.allowed:
                journal.write(
                    "blocked",
                    coin=coin,
                    reason=decision.reason,
                    side=signal.side,
                    imbalance=signal.imbalance,
                )
                continue
            sized = size_notional(settings, signal, risk.state.equity_usd)
            if sized.notional_usd <= 0:
                journal.write("blocked", coin=coin, reason=sized.reason)
                continue
            try:
                fill = executor.submit(signal, sized.notional_usd)
            except LiveTradingDisabled as exc:
                journal.write("live_refused", error=str(exc))
                raise
            risk.state.open_positions += 1
            open_pos = PaperPosition(
                fill=fill,
                entry_mid=signal.mid,
                opened_at=datetime.now(UTC),
                hold_seconds=settings.hold_seconds,
            )
            journal.write(
                "fill",
                fill_id=fill.fill_id,
                coin=fill.coin,
                side=fill.side,
                qty=fill.qty,
                px=fill.px,
                fee_usd=fill.fee_usd,
                status=fill.status,
                notional_usd=sized.notional_usd,
                edge_score=signal.edge_score,
                imbalance=signal.imbalance,
                spread_bps=signal.spread_bps,
            )
            break  # one entry per tick

        heartbeat.beat(
            mode=args.mode,
            coins=settings.coins,
            extra={
                "ticks": ticks,
                "open": open_pos.fill.coin if open_pos else None,
                "day_pnl_usd": risk.state.day_pnl_usd,
                "killed": risk.state.killed,
            },
        )

    if args.once:
        # Accelerate hold expiry for --once demos: still run entry then exit path.
        try:
            tick()
            if open_pos is not None:
                open_pos.hold_seconds = 0
                # Re-fetch books for exit mark
                books = {}
                for coin in settings.coins:
                    book = feed.l2_book(coin)
                    if book is not None:
                        books[coin] = book
                manage_exit(books)
        except LiveTradingDisabled:
            return 3
        except Exception as exc:  # noqa: BLE001
            journal.write("crash", error=str(exc), traceback=traceback.format_exc())
            return 1
        return 0

    print(f"hl_scalper mode={args.mode} coins={','.join(settings.coins)} data={settings.data_dir}")
    while True:
        try:
            tick()
        except LiveTradingDisabled:
            return 3
        except Exception as exc:  # noqa: BLE001
            journal.write("crash", error=str(exc), traceback=traceback.format_exc())
            # Keep daemon alive unless kill switch tripped by feed budget.
        time.sleep(settings.poll_interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
