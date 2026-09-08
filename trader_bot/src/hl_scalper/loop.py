from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

from hl_scalper.agents import AgentDesk
from hl_scalper.arming import check_arming
from hl_scalper.config import Settings
from hl_scalper.execution import LiveTradingDisabled, build_executor
from hl_scalper.execution.maker import PaperMakerBook, QuoteBook, RestingQuote
from hl_scalper.feed import L2Book
from hl_scalper.feed.ws import HybridBookFeed, build_feed
from hl_scalper.journal import Heartbeat, Journal
from hl_scalper.position import PaperPosition, close_from_fill, decide_exit
from hl_scalper.reconcile import ClearinghouseClient, reconcile_flat_local
from hl_scalper.risk import RiskGate
from hl_scalper.sizer import size_notional
from hl_scalper.strategy import StrategyParams, evaluate
from hl_scalper.strategy.maker import MakerParams, plan_maker_quotes
from hl_scalper.ui_state import publish_runtime


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
    parser.add_argument(
        "--ensemble",
        action="store_true",
        help="Multi-agent desk (imbalance+funding+liquidity+spread); disagreement sits out",
    )
    parser.add_argument(
        "--maker",
        action="store_true",
        help="Enable S2 maker post-only paper quotes (join touch; cancel/fill from L2)",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    overrides: dict[str, object] = {
        "coins": tuple(c.strip().upper() for c in args.coins.split(",") if c.strip()),
        "poll_interval_s": args.interval if args.interval is not None else Settings.poll_interval_s,
        "hold_seconds": args.hold_seconds if args.hold_seconds is not None else Settings.hold_seconds,
        "data_dir": str(data_dir),
        "journal_path": str(data_dir / "journal.jsonl"),
        "heartbeat_path": str(data_dir / "heartbeat.json"),
        "books_path": str(data_dir / "books.jsonl"),
        "arm_file": str(data_dir / "ARMED"),
        "record_books": bool(args.record_books),
        "use_ws": False if args.no_ws else Settings.use_ws,
    }
    if args.ensemble:
        overrides["ensemble"] = True
    if args.maker:
        overrides["maker_enabled"] = True
    settings = Settings.from_env(**overrides)
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
    desk = AgentDesk(settings, risk) if settings.ensemble else None
    maker_book = PaperMakerBook(settings) if settings.maker_enabled else None
    maker_params = MakerParams(
        spread_bps_max=settings.maker_spread_bps_max,
        min_notional=settings.min_notional,
        book_levels=settings.book_levels,
        lean=settings.maker_lean,
        cancel_bps=settings.maker_cancel_bps,
        join_inside_bps=settings.maker_join_inside_bps,
        twosided=settings.maker_twosided,
    )
    reconciler = ClearinghouseClient(info_url=settings.info_url)
    master = os.environ.get("HL_MASTER_ADDRESS", "").strip()
    open_pos: PaperPosition | None = None
    quote_book = QuoteBook()
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
        dry_run_live=settings.dry_run_live,
        allow_live_orders=settings.allow_live_orders,
        ensemble=settings.ensemble,
        ensemble_min_agree=settings.ensemble_min_agree,
        maker_enabled=settings.maker_enabled,
        maker_fee_bps=settings.maker_fee_bps,
        maker_twosided=settings.maker_twosided,
    )
    publish_runtime(
        data_dir,
        settings=settings,
        mode=args.mode,
        risk=risk,
        open_pos=None,
        books=None,
        ticks=0,
    )

    def beat(books: dict[str, L2Book] | None = None) -> None:
        publish_runtime(
            data_dir,
            settings=settings,
            mode=args.mode,
            risk=risk,
            open_pos=open_pos,
            books=books,
            ticks=ticks,
        )
        heartbeat.beat(
            mode=args.mode,
            coins=settings.coins,
            extra={
                "ticks": ticks,
                "open": open_pos.fill.coin if open_pos else None,
                "quotes": [f"{q.coin}:{q.side}@{q.limit_px}" for q in quote_book.quotes.values()],
                "day_pnl_usd": risk.state.day_pnl_usd,
                "killed": risk.state.killed,
                "kill_reason": risk.state.kill_reason or None,
            },
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
        try:
            close_fill = executor.close_position(open_pos, decision.exit_mid)
        except LiveTradingDisabled as exc:
            journal.write("live_refused", error=str(exc), phase="close")
            raise
        closed = close_from_fill(
            open_pos,
            close_fill,
            reason=decision.reason,
        )
        risk.state.open_positions = max(0, risk.state.open_positions - 1)
        risk.record_pnl(closed.pnl_usd)
        for q in list(quote_book.all_for_coin(closed.coin)):
            _cancel_quote(q, "position_closed")
        journal.write(
            "exit",
            fill_id=closed.fill_id,
            close_fill_id=close_fill.fill_id,
            close_status=close_fill.status,
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

    def _cancel_quote(quote: RestingQuote, reason: str) -> None:
        journal.write(
            "quote_cancel",
            coin=quote.coin,
            side=quote.side,
            limit_px=quote.limit_px,
            reason=reason,
            cloid=quote.cloid,
        )
        quote_book.remove(quote)

    def _place_quote(signal, notional_usd: float) -> RestingQuote | None:
        if maker_book is None:
            return None
        existing = quote_book.get(signal.coin, signal.side)
        if existing is not None:
            # Refresh if price drifted; else keep resting.
            if signal.limit_px is not None and abs(existing.limit_px - signal.limit_px) / signal.limit_px < 1e-8:
                return existing
            _cancel_quote(existing, "reprice")
        quote = maker_book.place(signal, notional_usd)
        quote_book.upsert(quote)
        journal.write(
            "quote_place",
            coin=quote.coin,
            side=quote.side,
            limit_px=quote.limit_px,
            qty=quote.qty,
            notional_usd=quote.notional_usd,
            cloid=quote.cloid,
            reason=quote.reason,
            maker_fee_bps=settings.maker_fee_bps,
            twosided=settings.maker_twosided,
        )
        return quote

    def manage_quotes(books: dict[str, L2Book]) -> None:
        nonlocal open_pos
        if maker_book is None:
            return
        # Poll resting quotes.
        for quote in list(quote_book.quotes.values()):
            book = books.get(quote.coin)
            outcome, fill, why = maker_book.poll(quote, book)
            if outcome == "rest":
                continue
            if outcome == "cancel":
                _cancel_quote(quote, why)
                continue
            assert fill is not None
            # First fill wins inventory; cancel sibling quotes on this coin.
            for other in quote_book.all_for_coin(quote.coin):
                if other.cloid != quote.cloid:
                    _cancel_quote(other, "sibling_filled")
            quote_book.remove(quote)
            if open_pos is not None:
                # Opposite-side fill flattens inventory; same-side is unexpected.
                if fill.side == open_pos.fill.side:
                    journal.write(
                        "quote_cancel",
                        coin=quote.coin,
                        side=quote.side,
                        limit_px=quote.limit_px,
                        reason="fill_while_open_same_side",
                        cloid=quote.cloid,
                    )
                    continue
                closed = close_from_fill(open_pos, fill, reason="maker_flatten")
                risk.state.open_positions = max(0, risk.state.open_positions - 1)
                risk.record_pnl(closed.pnl_usd)
                journal.write(
                    "exit",
                    fill_id=closed.fill_id,
                    close_fill_id=fill.fill_id,
                    close_status=fill.status,
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
                    execution="maker",
                )
                open_pos = None
                continue
            risk.state.open_positions += 1
            open_pos = PaperPosition(
                fill=fill,
                entry_mid=quote.placed_mid,
                opened_at=datetime.now(UTC),
                hold_seconds=settings.hold_seconds,
                entry_imbalance=quote.imbalance,
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
                notional_usd=quote.notional_usd,
                edge_score=quote.edge_score,
                imbalance=quote.imbalance,
                spread_bps=quote.spread_bps,
                execution="maker",
                ensemble=bool(desk),
            )

        # Two-sided inventory quotes are solo --maker; ensemble places via ballot.
        if desk is not None:
            return

        inventory_coin = open_pos.fill.coin if open_pos else None
        inventory_side = open_pos.fill.side if open_pos else None

        for coin, book in books.items():
            if args.mode == "live" and coin not in settings.live_coins:
                continue
            if inventory_coin is not None and coin != inventory_coin:
                for q in quote_book.all_for_coin(coin):
                    _cancel_quote(q, "other_coin_open")
                continue

            inv = inventory_side if inventory_coin is not None else None
            wanted = plan_maker_quotes(book, inventory=inv, params=maker_params)
            wanted_sides = {s.side for s in wanted}
            for q in list(quote_book.all_for_coin(coin)):
                if q.side not in wanted_sides:
                    _cancel_quote(q, "inventory_skew")
            if risk.state.killed:
                continue
            for signal in wanted:
                # Never add size; only flatten when inventory is open.
                if open_pos is not None and signal.side == open_pos.fill.side:
                    continue
                reduce_only = open_pos is not None
                gate = risk.check(signal, book_age_s=book.age_s, reduce_only=reduce_only)
                if not gate.allowed:
                    continue
                sized = size_notional(settings, signal, risk.state.equity_usd)
                if sized.notional_usd <= 0:
                    continue
                if args.mode == "live":
                    journal.write(
                        "blocked",
                        coin=coin,
                        reason="maker_live_scaffold_paper_only",
                        execution="maker",
                    )
                    continue
                _place_quote(signal, sized.notional_usd)

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
        if risk.state.killed:
            for q in list(quote_book.quotes.values()):
                _cancel_quote(q, "killed")
        manage_quotes(books)

        if open_pos is not None or risk.state.killed:
            beat(books)
            return

        # Solo maker: quotes are maintained in manage_quotes; no taker entry loop.
        if settings.maker_enabled and desk is None:
            beat(books)
            return

        if not maybe_reconcile():
            beat(books)
            return

        for coin, book in books.items():
            if args.mode == "live" and coin not in settings.live_coins:
                continue

            if desk is not None:
                desk_decision = desk.evaluate_coin(book, now=time.monotonic())
                journal.write("ensemble", coin=coin, **desk.journal_payload(desk_decision))
                if desk_decision.action != "enter" or desk_decision.signal is None:
                    journal.write("sit_out", coin=coin, reason=desk_decision.reason)
                    continue
                signal = desk_decision.signal
            else:
                signal = evaluate(book, params)
                if signal is None:
                    journal.write("sit_out", coin=coin, reason="no_signal")
                    continue
                gate = risk.check(signal, book_age_s=book.age_s)
                if not gate.allowed:
                    journal.write(
                        "blocked",
                        coin=coin,
                        reason=gate.reason,
                        side=signal.side,
                        imbalance=signal.imbalance,
                    )
                    continue

            journal.write(
                "signal",
                coin=signal.coin,
                side=signal.side,
                imbalance=signal.imbalance,
                spread_bps=signal.spread_bps,
                mid=signal.mid,
                edge_score=signal.edge_score,
                reason=signal.reason,
                execution=signal.execution,
                limit_px=signal.limit_px,
            )
            sized = size_notional(settings, signal, risk.state.equity_usd)
            if sized.notional_usd <= 0:
                journal.write("blocked", coin=coin, reason=sized.reason)
                continue

            if signal.execution == "maker":
                if args.mode == "live":
                    journal.write(
                        "blocked",
                        coin=coin,
                        reason="maker_live_scaffold_paper_only",
                        execution="maker",
                    )
                    continue
                _place_quote(signal, sized.notional_usd)
                break

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
                execution="taker",
                ensemble=bool(desk),
            )
            break

        beat(books)

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
            f"hl_scalper mode={args.mode} ws={settings.use_ws} ensemble={settings.ensemble} "
            f"maker={settings.maker_enabled} coins={','.join(settings.coins)} data={settings.data_dir}"
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
