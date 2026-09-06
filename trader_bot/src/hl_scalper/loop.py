from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from hl_scalper.arming import check_arming
from hl_scalper.config import Settings
from hl_scalper.execution import LiveTradingDisabled, build_executor
from hl_scalper.feed import L2Book
from hl_scalper.feed.ws import HybridBookFeed, build_feed
from hl_scalper.journal import Heartbeat, Journal
from hl_scalper.position import PaperPosition, close_at_mid, decide_exit
from hl_scalper.reconcile import ClearinghouseClient, reconcile_flat_local
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
    parser.add_argument("--no-ws", action="store_true", help="Disable websocket books")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    settings = Settings.from_env(
        coins=tuple(c.strip().upper() for c in args.coins.split(",") if c.strip()),
        poll_interval_s=args.interval if args.interval is not None else Settings.poll_interval_s,
        hold_seconds=args.hold_seconds if args.hold_seconds is not None else Settings.hold_seconds,
        data_dir=str(data_dir),
        journal_path=str(data_dir / "journal.jsonl"),
        heartbeat_path=str(data_dir / "heartbeat.json"),
        books_path=str(data_dir / "books.jsonl"),
        arm_file=str(data_dir / "ARMED"),
        record_books=bool(args.record_books),
        use_ws=False if args.no_ws else Settings.use_ws,
    )
    if args.mode == "live":
        status = check_arming(
            live_enabled=settings.live_enabled,
            allow_live_orders=settings.allow_live_orders,
            arm_file=Path(settings.arm_file),
            killed=False,
        )
        if not status.ok:
            print(f"live mode refused: {status.summary}", file=sys.stderr)
            return 2

    settings.ensure_data_dirs()
    journal = Journal(Path(settings.journal_path))
    heartbeat = Heartbeat(Path(settings.heartbeat_path))
    books_journal = Journal(Path(settings.books_path)) if settings.record_books else None

    feed = build_feed(
        info_url=settings.info_url,
        coins=settings.coins,
        use_ws=settings.use_ws,
        max_ws_book_age_s=settings.max_ws_book_age_s,
    )
    risk = RiskGate(settings)
    executor = build_executor(settings, mode=args.mode)
    params = StrategyParams(
        imbalance_min=settings.imbalance_min,
        spread_bps_max=settings.spread_bps_max,
        min_notional=settings.min_notional,
        book_levels=settings.book_levels,
    )
    reconciler = ClearinghouseClient(info_url=settings.info_url)
    master = os.environ.get("HL_MASTER_ADDRESS", "").strip()
    open_pos: PaperPosition | None = None
    feed_failures = 0
    ticks = 0

    journal.write(
        "boot",
        mode=args.mode,
        coins=list(settings.coins),
        hold_seconds=settings.hold_seconds,
        equity_usd=settings.paper_equity_usd,
        use_ws=settings.use_ws,
        adverse_exit_bps=settings.adverse_exit_bps,
    )

    def manage_exit(books: dict[str, L2Book]) -> None:
        nonlocal open_pos
        if open_pos is None:
            return
        book = books.get(open_pos.fill.coin)
        decision = decide_exit(
            open_pos,
            book,
            strategy=params,
            adverse_bps=settings.adverse_exit_bps,
        )
        if not decision.should_exit or decision.reason is None or decision.exit_mid is None:
            return
        closed = close_at_mid(
            open_pos,
            decision.exit_mid,
            exit_fee_bps=settings.taker_fee_bps,
            reason=decision.reason,
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

    def maybe_reconcile() -> bool:
        if args.mode != "live" or not settings.reconcile_each_entry or not master:
            return True
        try:
            venue = reconciler.fetch(master)
        except Exception as exc:  # noqa: BLE001
            journal.write("reconcile_error", error=str(exc))
            return False
        result = reconcile_flat_local(
            local_open_coin=open_pos.fill.coin if open_pos else None,
            venue=venue,
        )
        journal.write(
            "reconcile",
            ok=result.ok,
            reason=result.reason,
            account_value=venue.account_value,
            n_positions=len(venue.positions),
        )
        if not result.ok:
            risk.trip(f"reconcile:{result.reason}")
            journal.write("kill", reason=risk.state.kill_reason)
            return False
        return True

    def tick() -> None:
        nonlocal open_pos, feed_failures, ticks
        ticks += 1
        books: dict[str, L2Book] = {}
        got_any = False
        for coin in settings.coins:
            try:
                book = feed.l2_book(coin)
            except Exception as exc:  # noqa: BLE001
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

        if not maybe_reconcile():
            heartbeat.beat(
                mode=args.mode,
                coins=settings.coins,
                extra={"ticks": ticks, "killed": True},
            )
            return

        for coin, book in books.items():
            if args.mode == "live" and coin not in settings.live_coins:
                continue
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
                entry_imbalance=signal.imbalance,
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
            break

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

    try:
        if args.once:
            try:
                tick()
                if open_pos is not None:
                    # Force time exit for --once demos after one more book pull.
                    open_pos.hold_seconds = 0
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

        print(
            f"hl_scalper mode={args.mode} ws={settings.use_ws} "
            f"coins={','.join(settings.coins)} data={settings.data_dir}"
        )
        while True:
            try:
                tick()
            except LiveTradingDisabled:
                return 3
            except Exception as exc:  # noqa: BLE001
                journal.write("crash", error=str(exc), traceback=traceback.format_exc())
            time.sleep(settings.poll_interval_s)
    finally:
        if isinstance(feed, HybridBookFeed):
            feed.close()


if __name__ == "__main__":
    raise SystemExit(main())
