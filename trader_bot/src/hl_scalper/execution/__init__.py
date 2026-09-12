from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from hl_scalper.arming import check_arming
from hl_scalper.config import Settings
from hl_scalper.exchange import HlExchangeClient, build_exchange_client_from_env
from hl_scalper.position import PaperPosition
from hl_scalper.sim import ioc_exit_limit_px, ioc_limit_px, taker_fee_usd
from hl_scalper.strategy import Signal
from hl_scalper.types import Fill

__all__ = [
    "Fill",
    "LiveTradingDisabled",
    "ExecutionPort",
    "PaperExecutor",
    "LiveExecutor",
    "build_executor",
]

logger = logging.getLogger(__name__)


class LiveTradingDisabled(RuntimeError):
    """Live Hyperliquid /exchange is not available / not armed."""


class ExecutionPort(Protocol):
    def submit(self, signal: Signal, notional_usd: float) -> Fill: ...

    def close_position(self, position: PaperPosition, exit_mid: float) -> Fill: ...


class PaperExecutor:
    """Paper path that mirrors HL IOC economics (slip + taker both sides)."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        size = min(notional_usd, self.settings.max_notional_usd)
        px = ioc_limit_px(
            side=signal.side,
            mid=signal.mid,
            spread_bps=signal.spread_bps,
            min_slip_bps=self.settings.ioc_slip_bps_min,
        )
        qty = size / px if px > 0 else 0.0
        fee = taker_fee_usd(size, self.settings.taker_fee_bps)
        return Fill(
            fill_id=str(uuid4()),
            coin=signal.coin,
            side=signal.side,
            qty=qty,
            px=px,
            fee_usd=fee,
            status="paper_fill",
            reason="paper_ioc_sim",
            created_at=datetime.now(UTC),
        )

    def close_position(self, position: PaperPosition, exit_mid: float) -> Fill:
        flatten_is_buy = position.fill.side == "sell"
        px = ioc_exit_limit_px(
            flatten_is_buy=flatten_is_buy,
            mid=exit_mid,
            min_slip_bps=self.settings.ioc_slip_bps_min,
        )
        notional = position.fill.qty * px
        fee = taker_fee_usd(notional, self.settings.taker_fee_bps)
        side = "buy" if flatten_is_buy else "sell"
        return Fill(
            fill_id=str(uuid4()),
            coin=position.fill.coin,
            side=side,
            qty=position.fill.qty,
            px=px,
            fee_usd=fee,
            status="paper_fill",
            reason="paper_ioc_close",
            created_at=datetime.now(UTC),
        )


class LiveExecutor:
    """Armed live path. Defaults to dry-run posts until DRY_RUN_LIVE=false."""

    def __init__(self, settings: Settings, client: HlExchangeClient | None = None) -> None:
        self.settings = settings
        self._client = client

    def _require_client(self) -> HlExchangeClient:
        if self._client is None:
            self._client = build_exchange_client_from_env(
                dry_run=self.settings.dry_run_live,
                info_url=self.settings.info_url,
            )
        return self._client

    def _assert_armed(self, coin: str) -> None:
        status = check_arming(
            live_enabled=self.settings.live_enabled,
            allow_live_orders=self.settings.allow_live_orders,
            arm_file=Path(self.settings.arm_file),
            killed=False,
        )
        if not status.ok:
            raise LiveTradingDisabled(f"live not armed: {status.summary}")
        if coin not in self.settings.live_coins:
            raise LiveTradingDisabled(f"coin {coin} not in live universe")

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        self._assert_armed(signal.coin)
        client = self._require_client()
        size = min(notional_usd, self.settings.max_notional_usd)
        limit_px = ioc_limit_px(
            side=signal.side,
            mid=signal.mid,
            spread_bps=signal.spread_bps,
            min_slip_bps=self.settings.ioc_slip_bps_min,
        )
        qty = size / limit_px if limit_px > 0 else 0.0
        if qty <= 0:
            raise LiveTradingDisabled("dust qty")
        result = client.marketable_ioc(
            coin=signal.coin,
            is_buy=signal.side == "buy",
            sz=qty,
            limit_px=limit_px,
            reduce_only=False,
        )
        if result.status == "dry_run":
            fill_px = limit_px
            fill_qty = qty
            status = "dry_run_fill"
        else:
            if not result.ok or not result.filled_sz or result.avg_px is None:
                raise LiveTradingDisabled(
                    f"ioc_not_filled:{result.status}:{result.reason or 'no_fill'}"
                )
            fill_px = float(result.avg_px)
            fill_qty = float(result.filled_sz)
            status = "filled"
        fee = taker_fee_usd(fill_qty * fill_px, self.settings.taker_fee_bps)
        return Fill(
            fill_id=result.intent.cloid,
            coin=signal.coin,
            side=signal.side,
            qty=fill_qty,
            px=fill_px,
            fee_usd=fee,
            status=status,
            reason=result.reason or "live_ioc",
            created_at=datetime.now(UTC),
        )

    def close_position(self, position: PaperPosition, exit_mid: float) -> Fill:
        self._assert_armed(position.fill.coin)
        client = self._require_client()
        is_buy = position.fill.side == "sell"  # flatten opposite
        limit_px = ioc_exit_limit_px(
            flatten_is_buy=is_buy,
            mid=exit_mid,
            min_slip_bps=self.settings.ioc_slip_bps_min,
        )
        result = client.marketable_ioc(
            coin=position.fill.coin,
            is_buy=is_buy,
            sz=position.fill.qty,
            limit_px=limit_px,
            reduce_only=True,
        )
        if result.status == "dry_run":
            fill_px = limit_px
            fill_qty = position.fill.qty
            status = "dry_run_fill"
        else:
            if not result.ok or not result.filled_sz or result.avg_px is None:
                raise LiveTradingDisabled(
                    f"ioc_close_not_filled:{result.status}:{result.reason or 'no_fill'}"
                )
            fill_px = float(result.avg_px)
            fill_qty = float(result.filled_sz)
            status = "filled"
        fee = taker_fee_usd(fill_qty * fill_px, self.settings.taker_fee_bps)
        return Fill(
            fill_id=result.intent.cloid,
            coin=position.fill.coin,
            side="buy" if is_buy else "sell",
            qty=fill_qty,
            px=fill_px,
            fee_usd=fee,
            status=status,
            reason=result.reason or "live_close",
            created_at=datetime.now(UTC),
        )


def build_executor(settings: Settings, *, mode: str) -> ExecutionPort:
    if mode == "live":
        return LiveExecutor(settings)
    return PaperExecutor(settings)
