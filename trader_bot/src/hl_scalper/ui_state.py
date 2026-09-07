from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from hl_scalper.arming import check_arming
from hl_scalper.config import Settings
from hl_scalper.feed import L2Book
from hl_scalper.journal import utc_now_iso
from hl_scalper.position import PaperPosition, mark_pnl
from hl_scalper.risk import RiskGate


def atomic_json(path: Path, body: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(dict(body), default=str) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def position_payload(
    open_pos: PaperPosition | None,
    books: Mapping[str, L2Book] | None = None,
    *,
    taker_fee_bps: float = 0.0,
) -> dict[str, Any]:
    if open_pos is None:
        return {"open": False, "ts": utc_now_iso()}
    fill = open_pos.fill
    book = (books or {}).get(fill.coin)
    mark_mid = book.mid if book is not None else None
    unrealized: float | None = None
    if mark_mid is not None and mark_mid > 0:
        exit_fee = abs(fill.qty) * mark_mid * (taker_fee_bps / 10_000.0)
        unrealized = mark_pnl(
            side=fill.side,
            qty=fill.qty,
            entry_px=fill.px,
            exit_px=mark_mid,
            entry_fee_usd=fill.fee_usd,
            exit_fee_usd=exit_fee,
        )
    opened = open_pos.opened_at
    if opened.tzinfo is None:
        opened = opened.replace(tzinfo=UTC)
    age_s = (datetime.now(UTC) - opened.astimezone(UTC)).total_seconds()
    return {
        "open": True,
        "ts": utc_now_iso(),
        "coin": fill.coin,
        "side": fill.side,
        "qty": fill.qty,
        "entry_px": fill.px,
        "entry_mid": open_pos.entry_mid,
        "opened_at": opened.isoformat(),
        "age_s": round(age_s, 3),
        "hold_seconds": open_pos.hold_seconds,
        "mark_mid": mark_mid,
        "unrealized_pnl_usd": unrealized,
        "entry_imbalance": open_pos.entry_imbalance,
        "fill_id": fill.fill_id,
        "status": fill.status,
    }


def status_payload(
    *,
    settings: Settings,
    mode: str,
    risk: RiskGate,
    ticks: int = 0,
) -> dict[str, Any]:
    arm_path = Path(settings.arm_file)
    arm = check_arming(
        live_enabled=settings.live_enabled,
        allow_live_orders=settings.allow_live_orders,
        arm_file=arm_path,
        killed=risk.state.killed,
    )
    return {
        "ts": utc_now_iso(),
        "mode": mode,
        "coins": list(settings.coins),
        "ensemble": settings.ensemble,
        "ensemble_min_agree": settings.ensemble_min_agree,
        "use_ws": settings.use_ws,
        "dry_run_live": settings.dry_run_live,
        "live_enabled": settings.live_enabled,
        "allow_live_orders": settings.allow_live_orders,
        "arm_file": str(arm_path),
        "arm_file_present": arm_path.is_file(),
        "armed": arm.ok,
        "arm_reasons": list(arm.reasons),
        "killed": risk.state.killed,
        "kill_reason": risk.state.kill_reason or None,
        "day_pnl_usd": risk.state.day_pnl_usd,
        "equity_usd": risk.state.equity_usd,
        "ticks": ticks,
        "hold_seconds": settings.hold_seconds,
        "data_dir": settings.data_dir,
    }


def publish_runtime(
    data_dir: Path,
    *,
    settings: Settings,
    mode: str,
    risk: RiskGate,
    open_pos: PaperPosition | None,
    books: Mapping[str, L2Book] | None,
    ticks: int,
) -> None:
    atomic_json(data_dir / "position.json", position_payload(open_pos, books, taker_fee_bps=settings.taker_fee_bps))
    atomic_json(
        data_dir / "status.json",
        status_payload(settings=settings, mode=mode, risk=risk, ticks=ticks),
    )
