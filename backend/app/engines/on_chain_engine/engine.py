"""On-chain / network activity engine for crypto."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.symbols import AssetClass, get_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_MEMPOOL_FEES = "https://mempool.space/api/v1/fees/recommended"
_CG_SIMPLE = "https://api.coingecko.com/api/v3/simple/price"
_FEES_CACHE: TTLCache[int | None] = TTLCache(ttl_seconds=300.0)
_CG_CACHE: TTLCache[dict[str, float] | None] = TTLCache(ttl_seconds=600.0)

# Watchlist crypto → CoinGecko ids
_COINGECKO_IDS: dict[str, str] = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "SUI": "sui",
    "XRP": "ripple",
    "ADA": "cardano",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "DOGE": "dogecoin",
    "DOT": "polkadot",
    "LTC": "litecoin",
    "ATOM": "cosmos",
    "NEAR": "near",
    "ARB": "arbitrum",
    "APT": "aptos",
    "INJ": "injective-protocol",
    "TAO": "bittensor",
    "WIF": "dogwifcoin",
    "PEPE": "pepe",
    "RENDER": "render-token",
    "FET": "fetch-ai",
    "TIA": "celestia",
    "SEI": "sei-network",
    "JUP": "jupiter-exchange-solana",
    "OP": "optimism",
}


@dataclass
class OnChainResult:
    """On-chain / network activity output."""

    score: float
    description: str


def score_from_btc_fee(sat_vb: int) -> tuple[float, str]:
    """Map BTC next-block fee pressure to score (calm supportive, fever crowded)."""
    if sat_vb <= 5:
        return clamp_score(60.0), f"BTC fees {sat_vb} sat/vB — quiet mempool"
    if sat_vb <= 20:
        return clamp_score(54.0), f"BTC fees {sat_vb} sat/vB — normal network load"
    if sat_vb <= 50:
        return clamp_score(46.0), f"BTC fees {sat_vb} sat/vB — elevated demand"
    return clamp_score(38.0), f"BTC fees {sat_vb} sat/vB — congested / speculative heat"


def score_from_vol_mcap(ratio: float) -> tuple[float, str]:
    """Map 24h volume / market-cap to activity quality."""
    pct = ratio * 100.0
    if pct < 2.0:
        return clamp_score(44.0), f"vol/mcap {pct:.1f}% — thin liquidity"
    if pct < 8.0:
        return clamp_score(58.0), f"vol/mcap {pct:.1f}% — healthy turnover"
    if pct < 20.0:
        return clamp_score(50.0), f"vol/mcap {pct:.1f}% — active trading"
    return clamp_score(40.0), f"vol/mcap {pct:.1f}% — manic turnover"


def fetch_btc_next_block_fee() -> int | None:
    """Recommended next-block fee from mempool.space."""

    def _load() -> int | None:
        try:
            with httpx.Client(timeout=8.0) as client:
                response = client.get(_MEMPOOL_FEES)
                response.raise_for_status()
                return int(response.json()["fastestFee"])
        except Exception:
            logger.exception("mempool.space fee fetch failed")
            return None

    return _FEES_CACHE.get_or_set("btc_fee", _load)


def fetch_vol_mcap(symbol: str) -> float | None:
    """Fetch 24h volume / market cap from CoinGecko for a crypto symbol."""
    cg_id = _COINGECKO_IDS.get(symbol.upper())
    if not cg_id:
        return None

    def _load() -> dict[str, float] | None:
        ids = ",".join(_COINGECKO_IDS.values())
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    _CG_SIMPLE,
                    params={
                        "ids": ids,
                        "vs_currencies": "usd",
                        "include_24hr_vol": "true",
                        "include_market_cap": "true",
                    },
                )
                response.raise_for_status()
                raw = response.json()
            out: dict[str, float] = {}
            for sym, coin_id in _COINGECKO_IDS.items():
                row = raw.get(coin_id) or {}
                mcap = float(row.get("usd_market_cap") or 0)
                vol = float(row.get("usd_24h_vol") or 0)
                if mcap > 0:
                    out[sym] = vol / mcap
            return out
        except Exception:
            logger.exception("CoinGecko vol/mcap fetch failed")
            return None

    mapping = _CG_CACHE.get_or_set("vol_mcap", _load)
    if not mapping:
        return None
    return mapping.get(symbol.upper())


class OnChainEngine:
    """Orthogonal crypto activity: BTC mempool fees + alt vol/mcap turnover."""

    def analyze(self, symbol: str) -> OnChainResult:
        """Return on-chain / activity assessment for crypto; neutral for equities."""
        normalized = symbol.upper()
        try:
            asset_class = get_asset_class(normalized)
        except ValueError:
            return OnChainResult(50.0, "On-Chain: untracked symbol — neutral")

        if asset_class != AssetClass.CRYPTO:
            return OnChainResult(
                50.0,
                "On-Chain: equity/ETF — not applicable (neutral)",
            )

        if normalized == "BTC":
            fee = fetch_btc_next_block_fee()
            if fee is None:
                # fall through to vol/mcap
                pass
            else:
                score, detail = score_from_btc_fee(fee)
                return OnChainResult(score, f"On-Chain: {detail}")

        ratio = fetch_vol_mcap(normalized)
        if ratio is None:
            return OnChainResult(50.0, "On-Chain: activity data unavailable — neutral")

        score, detail = score_from_vol_mcap(ratio)
        return OnChainResult(score, f"On-Chain: {detail}")

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return on-chain evidence."""
        del timeframe
        result = self.analyze(symbol)
        return [
            EvidenceItem(
                source="on_chain_engine",
                category=ScoringCategory.ON_CHAIN.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.ON_CHAIN],
                description=result.description,
            )
        ]
