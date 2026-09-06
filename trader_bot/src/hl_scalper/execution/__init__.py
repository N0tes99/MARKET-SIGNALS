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
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def submit(self, signal: Signal, notional_usd: float) -> Fill:
        size = min(notional_usd, self.settings.max_notional_usd)
        slip = signal.spread_bps / 20_000.0
        px = signal.mid * (1.0 + slip) if signal.side == "buy" else signal.mid * (1.0 - slip)
        qty = size / px if px > 0 else 0.0
        fee = size * (self.settings.taker_fee_bps / 10_000.0)
        return Fill(
            fill_id=str(uuid4()),
            coin=signal.coin,
            side=signal.side,
            qty=qty,
            px=px,
            fee_usd=fee,
            status="paper_fill",
            reason="paper_sim",
            created_at=datetime.now(UTC),
        )

    def close_position(self, position: PaperPosition, exit_mid: float) -> Fill:
        notional = position.fill.qty * exit_mid
        fee = notional * (self.settings.taker_fee_bps / 10_000.0)
        side = "sell" if position.fill.side == "buy" else "buy"
        return Fill(
            fill_id=str(uuid4()),
            coin=position.fill.coin,
            side=side,
            qty=position.fill.qty,
            px=exit_mid,
            fee_usd=fee,
            status="paper_fill",
            reason="paper_close",
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
        # Marketable: buy above mid, sell below mid by a small slip.
        slip = max(signal.spread_bps / 10_000.0, 0.0005)
        px = signal.mid * (1.0 + slip) if signal.side == "buy" else signal.mid * (1.0 - slip)
        qty = size / px if px > 0 else 0.0
        if qty <= 0:
            raise LiveTradingDisabled("dust qty")
        result = client.marketable_ioc(
            coin=signal.coin,
            is_buy=signal.side == "buy",
            sz=qty,
            limit_px=px,
            reduce_only=False,
        )
        fee = size * (self.settings.taker_fee_bps / 10_000.0)
        status = "dry_run_fill" if result.status == "dry_run" else result.status
        return Fill(
            fill_id=result.intent.cloid,
            coin=signal.coin,
            side=signal.side,
            qty=qty,
            px=px,
            fee_usd=fee,
            status=status,
            reason=result.reason or "live_ioc",
            created_at=datetime.now(UTC),
        )

    def close_position(self, position: PaperPosition, exit_mid: float) -> Fill:
        self._assert_armed(position.fill.coin)
        client = self._require_client()
        is_buy = position.fill.side == "sell"  # flatten opposite
        slip = 0.0005
        px = exit_mid * (1.0 + slip) if is_buy else exit_mid * (1.0 - slip)
        result = client.marketable_ioc(
            coin=position.fill.coin,
            is_buy=is_buy,
            sz=position.fill.qty,
            limit_px=px,
            reduce_only=True,
        )
        notional = position.fill.qty * px
        fee = notional * (self.settings.taker_fee_bps / 10_000.0)
        status = "dry_run_fill" if result.status == "dry_run" else result.status
        return Fill(
            fill_id=result.intent.cloid,
            coin=position.fill.coin,
            side="buy" if is_buy else "sell",
            qty=position.fill.qty,
            px=px,
            fee_usd=fee,
            status=status,
            reason=result.reason or "live_close",
            created_at=datetime.now(UTC),
        )


def build_executor(settings: Settings, *, mode: str) -> ExecutionPort:
    if mode == "live":
        return LiveExecutor(settings)
    return PaperExecutor(settings)
