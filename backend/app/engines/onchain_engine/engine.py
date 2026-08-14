"""On-chain / activity engine — BTC mempool+difficulty + alt vol/mcap proxies."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.engines.evidence_engine.types import EvidenceItem
from app.market_data.symbols import AssetClass, get_asset_class
from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory
from app.utils.http_client import shared_client
from app.utils.scoring_helpers import clamp_score
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_MEMPOOL_FEES = "https://mempool.space/api/v1/fees/recommended"
_MEMPOOL_DIFFICULTY = "https://mempool.space/api/v1/difficulty-adjustment"
_COINGECKO_SIMPLE = "https://api.coingecko.com/api/v3/simple/price"

_BTC_CACHE: TTLCache[dict | None] = TTLCache(ttl_seconds=300.0)
_DIFF_CACHE: TTLCache[dict | None] = TTLCache(ttl_seconds=600.0)
_CG_CACHE: TTLCache[dict[str, dict] | None] = TTLCache(ttl_seconds=300.0)
_CG_ALL_KEY = "watchlist"

# Watchlist symbols → CoinGecko ids
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
    """On-chain / activity analysis output."""

    score: float
    description: str


def score_btc_mempool(fastest_fee: float) -> tuple[float, str]:
    """Map BTC recommended fee (sat/vB) to congestion score."""
    if fastest_fee <= 5:
        return clamp_score(60.0), f"BTC mempool calm ({fastest_fee:.0f} sat/vB)"
    if fastest_fee <= 20:
        return clamp_score(52.0), f"BTC mempool normal ({fastest_fee:.0f} sat/vB)"
    if fastest_fee <= 50:
        return clamp_score(42.0), f"BTC mempool elevated ({fastest_fee:.0f} sat/vB)"
    return clamp_score(34.0), f"BTC mempool congested ({fastest_fee:.0f} sat/vB)"


def score_difficulty_progress(progress_percent: float) -> tuple[float, str]:
    """Mild tilt from difficulty epoch progress (late epoch = hashrate pressure)."""
    if progress_percent >= 90:
        return 46.0, f"difficulty epoch late ({progress_percent:.0f}%)"
    if progress_percent <= 15:
        return 54.0, f"difficulty epoch early ({progress_percent:.0f}%)"
    return 50.0, f"difficulty epoch mid ({progress_percent:.0f}%)"


def score_vol_mcap(ratio: float) -> tuple[float, str]:
    """Map 24h volume / market cap to speculative heat (high = caution)."""
    pct = ratio * 100
    if pct < 2:
        return clamp_score(58.0), f"quiet activity (vol/mcap {pct:.1f}%)"
    if pct < 8:
        return clamp_score(52.0), f"healthy activity (vol/mcap {pct:.1f}%)"
    if pct < 20:
        return clamp_score(44.0), f"elevated turnover (vol/mcap {pct:.1f}%)"
    return clamp_score(36.0), f"speculative heat (vol/mcap {pct:.1f}%)"


def blend_activity_with_change(
    vol_score: float,
    vol_desc: str,
    change_24h: float | None,
) -> tuple[float, str]:
    """Fold 24h price change as a light confirmation on top of vol/mcap."""
    if change_24h is None:
        return vol_score, vol_desc
    # Extreme up + hot vol → slightly more caution; dump + quiet → mild support
    adj = 0.0
    if change_24h >= 8 and vol_score <= 44:
        adj = -4.0
        tag = f"surge {change_24h:+.1f}%"
    elif change_24h <= -8 and vol_score >= 52:
        adj = 3.0
        tag = f"washout {change_24h:+.1f}%"
    else:
        tag = f"24h {change_24h:+.1f}%"
    return clamp_score(vol_score + adj), f"{vol_desc}; {tag}"


def _fetch_btc_fees() -> dict | None:
    def _load() -> dict | None:
        try:
            client = shared_client(timeout=3.0, name="mempool")
            response = client.get(_MEMPOOL_FEES)
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("mempool.space fees fetch failed")
            return None

    return _BTC_CACHE.get_or_set("fees", _load)


def _fetch_btc_difficulty() -> dict | None:
    def _load() -> dict | None:
        try:
            client = shared_client(timeout=3.0, name="mempool")
            response = client.get(_MEMPOOL_DIFFICULTY)
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("mempool.space difficulty fetch failed")
            return None

    return _DIFF_CACHE.get_or_set("difficulty", _load)


def _fetch_coingecko_batch(ids: list[str]) -> dict[str, dict] | None:
    # Prefer the shared watchlist cache when the requested ids are a subset.
    cached_all = _CG_CACHE.get(_CG_ALL_KEY)
    if cached_all is not None:
        return cached_all

    key = ",".join(sorted(ids))

    def _load() -> dict[str, dict] | None:
        try:
            client = shared_client(timeout=4.0, name="coingecko")
            response = client.get(
                _COINGECKO_SIMPLE,
                params={
                    "ids": ",".join(ids),
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("CoinGecko activity fetch failed")
            return None

    return _CG_CACHE.get_or_set(key, _load)


def warm_coingecko_activity() -> None:
    """Prefetch vol/mcap for the full crypto watchlist in one HTTP call."""
    ids = list(_COINGECKO_IDS.values())

    def _load() -> dict[str, dict] | None:
        try:
            client = shared_client(timeout=4.0, name="coingecko")
            response = client.get(
                _COINGECKO_SIMPLE,
                params={
                    "ids": ",".join(ids),
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                },
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            logger.exception("CoinGecko watchlist warm failed")
            return None

    _CG_CACHE.get_or_set(_CG_ALL_KEY, _load)


class OnChainEngine:
    """Orthogonal crypto activity signals (mempool / difficulty / vol-mcap)."""

    def analyze(self, symbol: str) -> OnChainResult:
        """Return on-chain or activity proxy score for symbol."""
        normalized = symbol.upper()
        try:
            asset_class = get_asset_class(normalized)
        except ValueError:
            return OnChainResult(50.0, "On-Chain: untracked symbol — neutral")

        if asset_class != AssetClass.CRYPTO:
            return OnChainResult(
                50.0,
                f"On-Chain: N/A for {asset_class.value}",
            )

        if normalized == "BTC":
            parts: list[str] = []
            scores: list[float] = []
            fees = _fetch_btc_fees()
            if fees and "fastestFee" in fees:
                fee_score, fee_desc = score_btc_mempool(float(fees["fastestFee"]))
                scores.append(fee_score)
                parts.append(fee_desc)
            diff = _fetch_btc_difficulty()
            progress = None
            if isinstance(diff, dict):
                progress = diff.get("progressPercent")
            if progress is not None:
                d_score, d_desc = score_difficulty_progress(float(progress))
                scores.append(d_score)
                parts.append(d_desc)
            if not scores:
                return OnChainResult(50.0, "On-Chain: BTC mempool unavailable — neutral")
            blended = sum(scores) / len(scores)
            return OnChainResult(clamp_score(blended), f"On-Chain: {'; '.join(parts)}")

        cg_id = _COINGECKO_IDS.get(normalized)
        if not cg_id:
            return OnChainResult(50.0, f"On-Chain: no CoinGecko map for {normalized}")

        batch = _fetch_coingecko_batch([cg_id])
        if not batch or cg_id not in batch:
            return OnChainResult(50.0, f"On-Chain: activity data unavailable for {normalized}")

        row = batch[cg_id]
        mcap = float(row.get("usd_market_cap") or 0)
        vol = float(row.get("usd_24h_vol") or 0)
        change = row.get("usd_24h_change")
        change_f = float(change) if change is not None else None
        if mcap <= 0:
            return OnChainResult(50.0, f"On-Chain: {normalized} mcap missing — neutral")

        score, tone = score_vol_mcap(vol / mcap)
        score, tone = blend_activity_with_change(score, tone, change_f)
        return OnChainResult(score, f"On-Chain {normalized}: {tone}")

    def contribute_evidence(self, symbol: str, timeframe: str = "1h") -> list[EvidenceItem]:
        """Return on-chain evidence item."""
        del timeframe
        result = self.analyze(symbol)
        return [
            EvidenceItem(
                source="onchain_engine",
                category=ScoringCategory.ON_CHAIN.value,
                score=result.score,
                weight=DEFAULT_WEIGHTS[ScoringCategory.ON_CHAIN],
                description=result.description,
            )
        ]
