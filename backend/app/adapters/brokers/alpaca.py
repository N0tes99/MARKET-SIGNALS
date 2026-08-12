"""Alpaca Trading API — read-only mirror of account, positions, and fills.

Never places or cancels orders. Credentials come from env settings only.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import settings
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_DEFAULT_PAPER_URL = "https://paper-api.alpaca.markets"
_DEFAULT_LIVE_URL = "https://api.alpaca.markets"
_CACHE_TTL_SECONDS = 45.0
_MIRROR_CACHE: TTLCache["AlpacaMirrorSnapshot"] = TTLCache(ttl_seconds=_CACHE_TTL_SECONDS)


@dataclass(frozen=True)
class AlpacaPosition:
    symbol: str
    qty: float
    side: str
    market_value: float
    cost_basis: float
    unrealized_pl: float
    unrealized_plpc: float
    current_price: float
    avg_entry_price: float
    change_today: float


@dataclass(frozen=True)
class AlpacaFill:
    """Closed / filled order row used as a recent-fill mirror."""

    id: str
    symbol: str
    side: str
    qty: float
    filled_avg_price: float | None
    filled_at: datetime | None
    status: str
    order_type: str
    notional: float | None = None


@dataclass(frozen=True)
class AlpacaAccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    portfolio_value: float
    status: str
    currency: str = "USD"


@dataclass
class AlpacaMirrorSnapshot:
    """Dashboard payload for the Alpaca read-only mirror."""

    configured: bool
    mode: str  # unconfigured | paper | live
    base_url: str
    as_of: datetime
    cached: bool = False
    error: str | None = None
    account: AlpacaAccountSnapshot | None = None
    positions: list[AlpacaPosition] = field(default_factory=list)
    recent_fills: list[AlpacaFill] = field(default_factory=list)


def alpaca_configured() -> bool:
    """True when both API key and secret are set."""
    return bool(
        (settings.alpaca_api_key or "").strip()
        and (settings.alpaca_api_secret or "").strip()
    )


def _resolve_base_url() -> str:
    override = (settings.alpaca_base_url or "").strip().rstrip("/")
    if override:
        return override
    return _DEFAULT_PAPER_URL


def _detect_mode(base_url: str) -> str:
    lowered = base_url.lower()
    if "paper-api" in lowered:
        return "paper"
    if "api.alpaca.markets" in lowered and "paper" not in lowered:
        return "live"
    return "custom"


def _auth_headers() -> dict[str, str]:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key.strip(),
        "APCA-API-SECRET-KEY": settings.alpaca_api_secret.strip(),
        "Accept": "application/json",
    }


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        # Alpaca returns RFC3339 with Z
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_position(row: dict[str, Any]) -> AlpacaPosition:
    qty = _parse_float(row.get("qty"))
    side = str(row.get("side") or ("long" if qty >= 0 else "short"))
    return AlpacaPosition(
        symbol=str(row.get("symbol") or ""),
        qty=qty,
        side=side,
        market_value=_parse_float(row.get("market_value")),
        cost_basis=_parse_float(row.get("cost_basis")),
        unrealized_pl=_parse_float(row.get("unrealized_pl")),
        unrealized_plpc=_parse_float(row.get("unrealized_plpc")),
        current_price=_parse_float(row.get("current_price")),
        avg_entry_price=_parse_float(row.get("avg_entry_price")),
        change_today=_parse_float(row.get("change_today")),
    )


def _parse_fill(row: dict[str, Any]) -> AlpacaFill | None:
    status = str(row.get("status") or "")
    filled_qty = _parse_float(row.get("filled_qty"))
    if filled_qty <= 0 and status not in {"filled", "partially_filled"}:
        return None
    qty = filled_qty if filled_qty > 0 else _parse_float(row.get("qty"))
    if qty <= 0:
        return None
    return AlpacaFill(
        id=str(row.get("id") or ""),
        symbol=str(row.get("symbol") or ""),
        side=str(row.get("side") or ""),
        qty=qty,
        filled_avg_price=(
            _parse_float(row.get("filled_avg_price"))
            if row.get("filled_avg_price") not in (None, "")
            else None
        ),
        filled_at=_parse_dt(row.get("filled_at") or row.get("updated_at")),
        status=status,
        order_type=str(row.get("type") or row.get("order_type") or ""),
        notional=(
            _parse_float(row.get("notional"))
            if row.get("notional") not in (None, "")
            else None
        ),
    )


def _parse_account(row: dict[str, Any]) -> AlpacaAccountSnapshot:
    equity = _parse_float(row.get("equity"))
    portfolio = _parse_float(row.get("portfolio_value"), default=equity)
    return AlpacaAccountSnapshot(
        equity=equity,
        cash=_parse_float(row.get("cash")),
        buying_power=_parse_float(row.get("buying_power")),
        portfolio_value=portfolio,
        status=str(row.get("status") or ""),
        currency=str(row.get("currency") or "USD"),
    )


def _unconfigured_snapshot() -> AlpacaMirrorSnapshot:
    return AlpacaMirrorSnapshot(
        configured=False,
        mode="unconfigured",
        base_url="",
        as_of=datetime.now(UTC),
        error=None,
        account=None,
        positions=[],
        recent_fills=[],
    )


def _fetch_mirror_uncached(*, fill_limit: int = 30) -> AlpacaMirrorSnapshot:
    if not alpaca_configured():
        return _unconfigured_snapshot()

    base_url = _resolve_base_url()
    mode = _detect_mode(base_url)
    headers = _auth_headers()
    as_of = datetime.now(UTC)

    try:
        with httpx.Client(timeout=12.0, headers=headers) as client:
            account_resp = client.get(f"{base_url}/v2/account")
            account_resp.raise_for_status()
            account = _parse_account(account_resp.json())

            positions_resp = client.get(f"{base_url}/v2/positions")
            positions_resp.raise_for_status()
            positions_raw = positions_resp.json()
            positions = [
                _parse_position(row)
                for row in positions_raw
                if isinstance(row, dict)
            ]
            positions.sort(key=lambda p: abs(p.market_value), reverse=True)

            orders_resp = client.get(
                f"{base_url}/v2/orders",
                params={
                    "status": "closed",
                    "limit": fill_limit,
                    "direction": "desc",
                    "nested": "false",
                },
            )
            orders_resp.raise_for_status()
            orders_raw = orders_resp.json()
            fills: list[AlpacaFill] = []
            for row in orders_raw:
                if not isinstance(row, dict):
                    continue
                fill = _parse_fill(row)
                if fill is not None:
                    fills.append(fill)

        return AlpacaMirrorSnapshot(
            configured=True,
            mode=mode,
            base_url=base_url,
            as_of=as_of,
            cached=False,
            error=None,
            account=account,
            positions=positions,
            recent_fills=fills,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        # Never log secrets; status + body snippet only.
        detail = (exc.response.text or "")[:200]
        logger.warning("Alpaca mirror HTTP %s: %s", status, detail)
        return AlpacaMirrorSnapshot(
            configured=True,
            mode=mode,
            base_url=base_url,
            as_of=as_of,
            error=f"Alpaca API error ({status})",
            account=None,
            positions=[],
            recent_fills=[],
        )
    except Exception as exc:
        logger.exception("Alpaca mirror fetch failed")
        return AlpacaMirrorSnapshot(
            configured=True,
            mode=mode,
            base_url=base_url,
            as_of=as_of,
            error=f"Alpaca mirror unavailable: {type(exc).__name__}",
            account=None,
            positions=[],
            recent_fills=[],
        )


def fetch_alpaca_mirror(*, use_cache: bool = True, fill_limit: int = 30) -> AlpacaMirrorSnapshot:
    """Return a short-TTL cached mirror snapshot (or fresh on demand)."""
    if not alpaca_configured():
        return _unconfigured_snapshot()

    if not use_cache:
        return _fetch_mirror_uncached(fill_limit=fill_limit)

    cache_key = f"mirror:{fill_limit}"
    hit = _MIRROR_CACHE.get(cache_key)
    if hit is not None:
        return AlpacaMirrorSnapshot(
            configured=hit.configured,
            mode=hit.mode,
            base_url=hit.base_url,
            as_of=hit.as_of,
            cached=True,
            error=hit.error,
            account=hit.account,
            positions=list(hit.positions),
            recent_fills=list(hit.recent_fills),
        )

    snap = _fetch_mirror_uncached(fill_limit=fill_limit)
    snap.cached = False
    _MIRROR_CACHE.set(cache_key, snap)
    return snap


def clear_alpaca_mirror_cache() -> None:
    """Test helper — drop in-memory mirror cache."""
    _MIRROR_CACHE.clear()
