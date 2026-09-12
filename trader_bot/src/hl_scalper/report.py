from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Report:
    fills: int = 0
    exits: int = 0
    signals: int = 0
    sit_outs: int = 0
    blocked: int = 0
    kills: int = 0
    wins: int = 0
    losses: int = 0
    pnl_usd: float = 0.0
    fees_usd: float = 0.0
    exit_reasons: Counter[str] | None = None

    def __post_init__(self) -> None:
        if self.exit_reasons is None:
            self.exit_reasons = Counter()

    @property
    def expectancy(self) -> float | None:
        if self.exits <= 0:
            return None
        return self.pnl_usd / self.exits

    @property
    def win_rate(self) -> float | None:
        n = self.wins + self.losses
        if n <= 0:
            return None
        return self.wins / n


def analyze_journal(path: Path) -> Report:
    report = Report()
    if not path.is_file():
        return report
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = row.get("event")
            if event == "signal":
                report.signals += 1
            elif event == "sit_out":
                report.sit_outs += 1
            elif event == "blocked":
                report.blocked += 1
            elif event == "kill":
                report.kills += 1
            elif event == "fill":
                report.fills += 1
                report.fees_usd += float(row.get("fee_usd") or 0)
            elif event == "exit":
                report.exits += 1
                pnl = float(row.get("pnl_usd") or 0)
                report.pnl_usd += pnl
                report.fees_usd += float(row.get("entry_fee_usd") or 0) + float(
                    row.get("exit_fee_usd") or 0
                )
                if pnl > 0:
                    report.wins += 1
                elif pnl < 0:
                    report.losses += 1
                reason = str(row.get("reason") or "unknown")
                assert report.exit_reasons is not None
                report.exit_reasons[reason] += 1
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HL scalper journal expectancy report")
    parser.add_argument("--journal", default="data/journal.jsonl")
    args = parser.parse_args(argv)
    report = analyze_journal(Path(args.journal))
    print(f"journal={args.journal}")
    print(f"signals={report.signals} sit_outs={report.sit_outs} blocked={report.blocked}")
    print(f"fills={report.fills} exits={report.exits} kills={report.kills}")
    print(f"wins={report.wins} losses={report.losses} win_rate={report.win_rate}")
    print(f"pnl_usd={report.pnl_usd:.4f} fees_usd={report.fees_usd:.4f}")
    print(f"expectancy_per_exit={report.expectancy}")
    print(f"exit_reasons={dict(report.exit_reasons or {})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
