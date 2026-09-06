from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from hl_scalper.config import Settings
from hl_scalper.execution import LiveTradingDisabled, build_executor
from hl_scalper.feed import HttpInfoFeed
from hl_scalper.risk import RiskGate
from hl_scalper.strategy import StrategyParams, evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HL book-imbalance scalper lab")
    parser.add_argument("--mode", choices=("paper", "live"), default="paper")
    parser.add_argument("--coins", default="BTC,ETH,SOL,HYPE")
    parser.add_argument("--once", action="store_true", help="Single poll then exit")
    parser.add_argument("--interval", type=float, default=None)
    args = parser.parse_args(argv)

    settings = Settings(
        coins=tuple(c.strip().upper() for c in args.coins.split(",") if c.strip()),
        poll_interval_s=args.interval or Settings.poll_interval_s,
    )
    if args.mode == "live" and not settings.live_enabled:
        print("live mode refused: settings.live_enabled is False", file=sys.stderr)
        return 2

    feed = HttpInfoFeed(base_url=settings.info_url)
    risk = RiskGate(settings)
    executor = build_executor(settings, mode=args.mode)
    params = StrategyParams(
        imbalance_min=settings.imbalance_min,
        spread_bps_max=settings.spread_bps_max,
        min_notional=settings.min_notional,
        book_levels=settings.book_levels,
    )
    journal = Path(settings.journal_path)
    journal.parent.mkdir(parents=True, exist_ok=True)

    def tick() -> None:
        for coin in settings.coins:
            book = feed.l2_book(coin)
            if book is None:
                _log(journal, {"event": "sit_out", "coin": coin, "reason": "no_book"})
                continue
            signal = evaluate(book, params)
            if signal is None:
                _log(journal, {"event": "sit_out", "coin": coin, "reason": "no_signal"})
                continue
            decision = risk.check(signal, book_age_s=book.age_s)
            if not decision.allowed:
                _log(
                    journal,
                    {
                        "event": "blocked",
                        "coin": coin,
                        "reason": decision.reason,
                        "side": signal.side,
                        "imbalance": signal.imbalance,
                    },
                )
                continue
            try:
                fill = executor.submit(signal, settings.max_notional_usd)
            except LiveTradingDisabled as exc:
                _log(journal, {"event": "live_refused", "error": str(exc)})
                raise
            risk.state.open_positions += 1
            _log(
                journal,
                {
                    "event": "fill",
                    "fill_id": fill.fill_id,
                    "coin": fill.coin,
                    "side": fill.side,
                    "qty": fill.qty,
                    "px": fill.px,
                    "fee_usd": fill.fee_usd,
                    "status": fill.status,
                    "edge_score": signal.edge_score,
                    "imbalance": signal.imbalance,
                    "spread_bps": signal.spread_bps,
                },
            )
            # Phase 0: flat immediately after entry mark (no hold model yet).
            risk.state.open_positions = max(0, risk.state.open_positions - 1)

    if args.once:
        tick()
        return 0

    print(f"hl_scalper mode={args.mode} coins={','.join(settings.coins)} (Ctrl+C to stop)")
    while True:
        tick()
        time.sleep(settings.poll_interval_s)


def _log(path: Path, row: dict[str, object]) -> None:
    row = {**row, "ts": datetime.now(UTC).isoformat()}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, default=str) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
