"""Deep derivatives snapshots — Binance (optional) → Bybit → OKX."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.market_data.symbols import to_binance_symbol
from app.utils.http_client import shared_client
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_BYBIT_BASE = "https://api.bybit.com"
_OKX_BASE = "https://www.okx.com"


@dataclass
class DerivativesDepth:
    """Funding + OI with short history for crowding analysis."""

    symbol: str
    funding_rate: float | None = None
    open_interest: float | None = None
    mark_price: float | None = None
    funding_history: list[float] = field(default_factory=list)
    oi_history: list[float] = field(default_factory=list)
    source: str = ""


_DEPTH_CACHE: TTLCache[DerivativesDepth | None] = TTLCache(ttl_seconds=120.0)


def _oi_change_pct(oi_history: list[float]) -> float | None:
    if len(oi_history) < 2:
        return None
    start = oi_history[0]
    end = oi_history[-1]
    if start <= 0:
        return None
    return ((end - start) / start) * 100.0


def funding_trend(history: list[float]) -> float | None:
    """Positive = funding rising (longs getting more crowded)."""
    if len(history) < 4:
        return None
    early = sum(history[:3]) / 3
    late = sum(history[-3:]) / 3
    return late - early


def score_derivatives_composite(
    funding: float | None,
    history: list[float],
    oi_change_pct: float | None,
    liquidation_score: float | None = None,
    liquidation_note: str | None = None,
) -> tuple[float, str]:
    """Crowded vs empty composite from funding, OI Δ, and optional liquidations."""
    from app.utils.scoring_helpers import clamp_score

    if funding is None:
        return 50.0, "Derivatives data unavailable"

    funding_bps = funding * 10_000
    # Peak score near neutral funding
    score = 70.0 - abs(funding_bps) * 5.0

    trend = funding_trend(history)
    notes: list[str] = []

    if funding > 0.0005:
        notes.append("elevated long funding")
    elif funding < -0.0005:
        notes.append("negative funding (shorts paying)")
    else:
        notes.append("neutral funding")

    if trend is not None:
        trend_bps = trend * 10_000
        if trend_bps > 0.5:
            score -= 6.0
            notes.append("funding rising")
        elif trend_bps < -0.5:
            score += 4.0
            notes.append("funding easing")

    if oi_change_pct is not None:
        crowded = abs(funding_bps) >= 3.0 and oi_change_pct > 3.0
        unwind = oi_change_pct < -5.0
        if crowded:
            score -= 8.0
            notes.append(f"OI rising {oi_change_pct:+.1f}% (crowded)")
        elif unwind:
            score += 5.0
            notes.append(f"OI falling {oi_change_pct:+.1f}% (unwind)")
        else:
            notes.append(f"OI Δ {oi_change_pct:+.1f}%")

    if liquidation_score is not None and liquidation_note:
        # Blend ~30% toward liquidation tilt (funding/OI remain primary)
        score = score * 0.7 + liquidation_score * 0.3
        notes.append(liquidation_note)

    description = f"Funding {funding_bps:.2f} bps — {', '.join(notes)}"
    return clamp_score(score), description


def _http_get_json(
    client: httpx.Client,
    url: str,
    params: dict,
    *,
    soft_fail: bool = True,
) -> dict | list | None:
    """GET JSON; treat geo/auth blocks as soft misses."""
    response = client.get(url, params=params)
    if response.status_code in {403, 404, 418, 451} and soft_fail:
        logger.debug("HTTP %s for %s params=%s", response.status_code, url, params)
        return None
    response.raise_for_status()
    return response.json()


def fetch_binance_depth(symbol: str, timeout: float = 2.0) -> DerivativesDepth | None:
    """Fetch Binance futures snapshot + funding/OI history."""
    try:
        pair = to_binance_symbol(symbol)
    except ValueError:
        return None

    base = settings.binance_futures_url
    try:
        client = shared_client(timeout=timeout, name="binance-futures-depth")
        premium_data = _http_get_json(
            client,
            f"{base}/fapi/v1/premiumIndex",
            {"symbol": pair},
        )
        if not isinstance(premium_data, dict):
            return None

        oi_data = _http_get_json(
            client,
            f"{base}/fapi/v1/openInterest",
            {"symbol": pair},
        )
        if not isinstance(oi_data, dict):
            return None

        funding_hist: list[float] = []
        fr = _http_get_json(
            client,
            f"{base}/fapi/v1/fundingRate",
            {"symbol": pair, "limit": 20},
        )
        if isinstance(fr, list):
            funding_hist = [float(row["fundingRate"]) for row in fr]

        oi_hist: list[float] = []
        oi_h = _http_get_json(
            client,
            f"{base}/futures/data/openInterestHist",
            {"symbol": pair, "period": "1h", "limit": 24},
        )
        if isinstance(oi_h, list):
            oi_hist = [float(row["sumOpenInterest"]) for row in oi_h]

        return DerivativesDepth(
            symbol=symbol.upper(),
            funding_rate=float(premium_data["lastFundingRate"]),
            open_interest=float(oi_data["openInterest"]),
            mark_price=float(premium_data["markPrice"]),
            funding_history=funding_hist,
            oi_history=oi_hist,
            source="binance",
        )
    except Exception:
        logger.debug("Binance derivatives depth failed for %s", symbol, exc_info=True)
        return None


def fetch_bybit_depth(symbol: str, timeout: float = 2.0) -> DerivativesDepth | None:
    """Fetch Bybit linear perpetuals snapshot + funding/OI history."""
    pair = f"{symbol.upper()}USDT"
    try:
        client = shared_client(timeout=timeout, name="bybit")
        payload = _http_get_json(
            client,
            f"{_BYBIT_BASE}/v5/market/tickers",
            {"category": "linear", "symbol": pair},
        )
        if not isinstance(payload, dict):
            return None
        rows = payload.get("result", {}).get("list", [])
        if not rows:
            return None
        tick = rows[0]

        funding_hist: list[float] = []
        fr = _http_get_json(
            client,
            f"{_BYBIT_BASE}/v5/market/funding/history",
            {"category": "linear", "symbol": pair, "limit": 20},
        )
        if isinstance(fr, dict):
            raw = fr.get("result", {}).get("list", [])
            funding_hist = list(reversed([float(row["fundingRate"]) for row in raw]))

        oi_hist: list[float] = []
        oi_h = _http_get_json(
            client,
            f"{_BYBIT_BASE}/v5/market/open-interest",
            {
                "category": "linear",
                "symbol": pair,
                "intervalTime": "1h",
                "limit": 24,
            },
        )
        if isinstance(oi_h, dict):
            raw_oi = oi_h.get("result", {}).get("list", [])
            oi_hist = list(reversed([float(row["openInterest"]) for row in raw_oi]))

        funding = tick.get("fundingRate")
        oi = tick.get("openInterest")
        mark = tick.get("markPrice")
        return DerivativesDepth(
            symbol=symbol.upper(),
            funding_rate=float(funding) if funding not in (None, "") else None,
            open_interest=float(oi) if oi not in (None, "") else None,
            mark_price=float(mark) if mark not in (None, "") else None,
            funding_history=funding_hist,
            oi_history=oi_hist,
            source="bybit",
        )
    except Exception:
        logger.debug("Bybit derivatives depth failed for %s", symbol, exc_info=True)
        return None


def fetch_okx_depth(symbol: str, timeout: float = 3.0) -> DerivativesDepth | None:
    """Fetch OKX USDT-SWAP funding — US-reachable when Bybit CloudFront blocks."""
    inst = f"{symbol.upper()}-USDT-SWAP"
    try:
        client = shared_client(timeout=timeout, name="okx")
        funding_payload = _http_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/funding-rate",
            {"instId": inst},
        )
        if not isinstance(funding_payload, dict) or funding_payload.get("code") != "0":
            return None
        rows = funding_payload.get("data") or []
        if not rows:
            return None
        funding_raw = rows[0].get("fundingRate")
        if funding_raw in (None, ""):
            return None

        funding_hist: list[float] = []
        hist_payload = _http_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/funding-rate-history",
            {"instId": inst, "limit": "20"},
        )
        if isinstance(hist_payload, dict) and hist_payload.get("code") == "0":
            # OKX returns newest first — reverse to oldest→newest like Bybit.
            raw = hist_payload.get("data") or []
            funding_hist = list(
                reversed([float(row["fundingRate"]) for row in raw if row.get("fundingRate")])
            )

        oi: float | None = None
        oi_payload = _http_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/open-interest",
            {"instType": "SWAP", "instId": inst},
        )
        if isinstance(oi_payload, dict) and oi_payload.get("code") == "0":
            oi_rows = oi_payload.get("data") or []
            if oi_rows and oi_rows[0].get("oi") not in (None, ""):
                oi = float(oi_rows[0]["oi"])

        mark: float | None = None
        mark_payload = _http_get_json(
            client,
            f"{_OKX_BASE}/api/v5/public/mark-price",
            {"instType": "SWAP", "instId": inst},
        )
        if isinstance(mark_payload, dict) and mark_payload.get("code") == "0":
            mark_rows = mark_payload.get("data") or []
            if mark_rows and mark_rows[0].get("markPx") not in (None, ""):
                mark = float(mark_rows[0]["markPx"])

        return DerivativesDepth(
            symbol=symbol.upper(),
            funding_rate=float(funding_raw),
            open_interest=oi,
            mark_price=mark,
            funding_history=funding_hist,
            oi_history=[oi] if oi is not None else [],
            source="okx",
        )
    except Exception:
        logger.debug("OKX derivatives depth failed for %s", symbol, exc_info=True)
        return None


def fetch_derivatives_depth(symbol: str) -> DerivativesDepth | None:
    """Binance (when allowed) → Bybit → OKX. OKX covers US / Render geo-blocks."""
    from app.market_data.providers.binance import use_binance

    key = symbol.upper()

    def _load() -> DerivativesDepth | None:
        if use_binance():
            depth = fetch_binance_depth(key)
            if depth is not None and depth.funding_rate is not None:
                return depth
        bybit = fetch_bybit_depth(key)
        if bybit is not None and bybit.funding_rate is not None:
            return bybit
        return fetch_okx_depth(key)

    return _DEPTH_CACHE.get_or_set(key, _load)


# Re-export helper used by scoring/tests
def oi_change_pct(oi_history: list[float]) -> float | None:
    return _oi_change_pct(oi_history)
