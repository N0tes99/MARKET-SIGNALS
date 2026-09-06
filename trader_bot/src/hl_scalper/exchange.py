from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


def _cloid() -> str:
    # 16-byte hex with 0x prefix for hyperliquid.utils.types.Cloid.from_str
    return "0x" + uuid4().hex[:32]


@dataclass(frozen=True)
class OrderIntent:
    coin: str
    is_buy: bool
    sz: float
    limit_px: float
    reduce_only: bool
    cloid: str
    dry_run: bool


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    status: str
    raw: dict[str, Any] | None
    intent: OrderIntent
    reason: str = ""


class HlExchangeClient:
    """Agent-wallet HL /exchange client.

    Uses the official SDK. Always construct only after arming checks pass.
    When dry_run=True, orders are logged and not posted.
    """

    def __init__(
        self,
        *,
        agent_private_key: str,
        master_address: str,
        base_url: str = "https://api.hyperliquid.xyz",
        dry_run: bool = True,
    ) -> None:
        if os.environ.get("HL_MASTER_PRIVATE_KEY"):
            raise RuntimeError("HL_MASTER_PRIVATE_KEY must never be set on the bot host")
        from eth_account import Account
        from hyperliquid.exchange import Exchange
        from hyperliquid.utils import constants

        key = agent_private_key.strip()
        if not key.startswith("0x"):
            key = "0x" + key
        wallet = Account.from_key(key)
        api_url = base_url.rstrip("/")
        # SDK expects API root; constants.MAINNET_API_URL is https://api.hyperliquid.xyz
        if api_url.endswith("/info"):
            api_url = api_url[: -len("/info")]
        if api_url.endswith("/exchange"):
            api_url = api_url[: -len("/exchange")]
        self._dry_run = dry_run
        self._master = master_address.strip()
        self._wallet_address = wallet.address
        self._exchange = Exchange(
            wallet,
            base_url=api_url or constants.MAINNET_API_URL,
            account_address=self._master,
        )
        logger.info(
            "hl exchange client ready agent=%s master=%s dry_run=%s",
            self._wallet_address,
            self._master,
            dry_run,
        )

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    def marketable_ioc(
        self,
        *,
        coin: str,
        is_buy: bool,
        sz: float,
        limit_px: float,
        reduce_only: bool = False,
        cloid: str | None = None,
    ) -> OrderResult:
        intent = OrderIntent(
            coin=coin,
            is_buy=is_buy,
            sz=sz,
            limit_px=limit_px,
            reduce_only=reduce_only,
            cloid=cloid or _cloid(),
            dry_run=self._dry_run,
        )
        if self._dry_run:
            return OrderResult(True, "dry_run", {"intent": intent.__dict__}, intent, "dry_run")

        from hyperliquid.utils.types import Cloid

        raw = self._exchange.order(
            coin,
            is_buy,
            sz,
            limit_px,
            {"limit": {"tif": "Ioc"}},
            reduce_only=reduce_only,
            cloid=Cloid.from_str(intent.cloid),
        )
        ok = isinstance(raw, dict)
        status = "submitted" if ok else "error"
        return OrderResult(ok=ok, status=status, raw=raw if isinstance(raw, dict) else None, intent=intent)


def build_exchange_client_from_env(*, dry_run: bool, info_url: str) -> HlExchangeClient:
    agent = os.environ.get("HL_AGENT_PRIVATE_KEY", "").strip()
    master = os.environ.get("HL_MASTER_ADDRESS", "").strip()
    if not agent or not master:
        raise RuntimeError("HL_AGENT_PRIVATE_KEY and HL_MASTER_ADDRESS required")
    base = info_url
    return HlExchangeClient(
        agent_private_key=agent,
        master_address=master,
        base_url=base,
        dry_run=dry_run,
    )
