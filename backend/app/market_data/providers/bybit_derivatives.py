"""Deep derivatives snapshots — Binance first, Bybit fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.market_data.symbols import to_binance_symbol

logger = logging.getLogger(__name__)

_BYBIT_BASE = "https://api.bybit.com"


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
) -> tuple[float, str]:
    """Crowded vs empty composite from funding level, trend, and OI Δ."""
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

    description = f"Funding {funding_bps:.2f} bps — {', '.join(notes)}"
    return clamp_score(score), description


def fetch_binance_depth(symbol: str, timeout: float = 10.0) -> DerivativesDepth | None:
    """Fetch Binance futures snapshot + funding/OI history."""
    try:
        pair = to_binance_symbol(symbol)
    except ValueError:
        return None

    base = settings.binance_futures_url
    try:
        with httpx.Client(timeout=timeout) as client:
            premium = client.get(f"{base}/fapi/v1/premiumIndex", params={"symbol": pair})
            premium.raise_for_status()
            premium_data = premium.json()

            oi = client.get(f"{base}/fapi/v1/openInterest", params={"symbol": pair})
            oi.raise_for_status()
            oi_data = oi.json()

            funding_hist: list[float] = []
            try:
                fr = client.get(
                    f"{base}/fapi/v1/fundingRate",
                    params={"symbol": pair, "limit": 20},
                )
                fr.raise_for_status()
                funding_hist = [float(row["fundingRate"]) for row in fr.json()]
            except Exception:
                logger.debug("Binance funding history unavailable for %s", symbol)

            oi_hist: list[float] = []
            try:
                oi_h = client.get(
                    f"{base}/futures/data/openInterestHist",
                    params={"symbol": pair, "period": "1h", "limit": 24},
                )
                oi_h.raise_for_status()
                oi_hist = [float(row["sumOpenInterest"]) for row in oi_h.json()]
            except Exception:
                logger.debug("Binance OI history unavailable for %s", symbol)

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
        logger.info("Binance derivatives depth failed for %s — will try Bybit", symbol)
        return None


def fetch_bybit_depth(symbol: str, timeout: float = 10.0) -> DerivativesDepth | None:
    """Fetch Bybit linear perpetuals snapshot + funding/OI history."""
    pair = f"{symbol.upper()}USDT"
    try:
        with httpx.Client(timeout=timeout) as client:
            tickers = client.get(
                f"{_BYBIT_BASE}/v5/market/tickers",
                params={"category": "linear", "symbol": pair},
            )
            tickers.raise_for_status()
            rows = tickers.json().get("result", {}).get("list", [])
            if not rows:
                return None
            tick = rows[0]

            funding_hist: list[float] = []
            try:
                fr = client.get(
                    f"{_BYBIT_BASE}/v5/market/funding/history",
                    params={"category": "linear", "symbol": pair, "limit": 20},
                )
                fr.raise_for_status()
                # Bybit returns newest first — reverse to oldest→newest
                raw = fr.json().get("result", {}).get("list", [])
                funding_hist = list(
                    reversed([float(row["fundingRate"]) for row in raw])
                )
            except Exception:
                logger.debug("Bybit funding history unavailable for %s", symbol)

            oi_hist: list[float] = []
            try:
                oi_h = client.get(
                    f"{_BYBIT_BASE}/v5/market/open-interest",
                    params={
                        "category": "linear",
                        "symbol": pair,
                        "intervalTime": "1h",
                        "limit": 24,
                    },
                )
                oi_h.raise_for_status()
                raw_oi = oi_h.json().get("result", {}).get("list", [])
                # Newest first
                oi_hist = list(
                    reversed([float(row["openInterest"]) for row in raw_oi])
                )
            except Exception:
                logger.debug("Bybit OI history unavailable for %s", symbol)

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
        logger.exception("Bybit derivatives depth failed for %s", symbol)
        return None


def fetch_derivatives_depth(symbol: str) -> DerivativesDepth | None:
    """Binance first; fall back to Bybit when Binance fails or is empty."""
    depth = fetch_binance_depth(symbol)
    if depth is not None and depth.funding_rate is not None:
        return depth
    return fetch_bybit_depth(symbol)


# Re-export helper used by scoring/tests
def oi_change_pct(oi_history: list[float]) -> float | None:
    return _oi_change_pct(oi_history)
