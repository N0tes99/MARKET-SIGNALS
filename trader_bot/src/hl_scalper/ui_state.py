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
    taker_fee_bps: float = 3.5,
    ioc_slip_bps_min: float = 5.0,
) -> dict[str, Any]:
    if open_pos is None:
        return {"open": False, "ts": utc_now_iso()}
    fill = open_pos.fill
    book = (books or {}).get(fill.coin)
    mark_mid = book.mid if book is not None else None
    unrealized: float | None = None
    mark_exit_px: float | None = None
    if mark_mid is not None and mark_mid > 0:
        from hl_scalper.sim import ioc_exit_limit_px, taker_fee_usd

        flatten_is_buy = fill.side == "sell"
        mark_exit_px = ioc_exit_limit_px(
            flatten_is_buy=flatten_is_buy,
            mid=mark_mid,
            min_slip_bps=ioc_slip_bps_min,
        )
        exit_fee = taker_fee_usd(abs(fill.qty) * mark_exit_px, taker_fee_bps)
        unrealized = mark_pnl(
            side=fill.side,
            qty=fill.qty,
            entry_px=fill.px,
            exit_px=mark_exit_px,
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
        "mark_exit_px": mark_exit_px,
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
    strategies = [
        {
            "id": "imbalance",
            "name": "S1 imbalance",
            "role": "L2 book imbalance scalp",
            "active": True,
            "solo_default": True,
        },
        {
            "id": "maker",
            "name": "S2 maker",
            "role": "post-only join quote",
            "active": bool(settings.maker_enabled),
            "solo_default": False,
        },
        {
            "id": "funding",
            "name": "S3 funding",
            "role": "funding extreme lean",
            "active": bool(settings.ensemble),
            "solo_default": False,
        },
        {
            "id": "liquidity",
            "name": "liquidity gate",
            "role": "spread/depth quality",
            "active": bool(settings.ensemble),
            "solo_default": False,
        },
        {
            "id": "spread_micro",
            "name": "S2-lite spread micro",
            "role": "tight-spread micro lean",
            "active": bool(settings.ensemble),
            "solo_default": False,
        },
        {
            "id": "risk",
            "name": "risk gate",
            "role": "fee/kill/cooldown veto",
            "active": True,
            "solo_default": True,
        },
    ]
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
        "taker_fee_bps": settings.taker_fee_bps,
        "maker_fee_bps": settings.maker_fee_bps,
        "maker_enabled": settings.maker_enabled,
        "ioc_slip_bps_min": settings.ioc_slip_bps_min,
        "fee_edge_buffer_bps": settings.fee_edge_buffer_bps,
        "strategies": strategies,
        "execution_model": "hl_ioc_taker+paper_maker",
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
    atomic_json(
        data_dir / "position.json",
        position_payload(
            open_pos,
            books,
            taker_fee_bps=settings.taker_fee_bps,
            ioc_slip_bps_min=settings.ioc_slip_bps_min,
        ),
    )
    atomic_json(
        data_dir / "status.json",
        status_payload(settings=settings, mode=mode, risk=risk, ticks=ticks),
    )
