"""Polite Reddit public JSON client (no OAuth) for ticker buzz."""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock

import httpx

from app.config import settings
from app.market_data.symbols import AssetClass, get_asset_class
from app.utils import disk_cache
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_SEARCH_BASE = "https://www.reddit.com"
_CACHE_TTL = 1_800.0  # 30 minutes
_MIN_REQUEST_GAP = 1.25  # polite spacing between live Reddit calls
_DISK_DIR = Path("/tmp/signal-engine/reddit")

_CRYPTO_SUBS = (
    "CryptoCurrency",
    "bitcoin",
    "ethereum",
    "ethtrader",
    "solana",
    "CryptoMarkets",
)
_EQUITY_SUBS = (
    "stocks",
    "options",
    "wallstreetbets",
    "investing",
    "StockMarket",
)

# Human-readable aliases improve search recall for tickers.
_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("Bitcoin", "BTC"),
    "ETH": ("Ethereum", "ETH"),
    "SOL": ("Solana", "SOL"),
    "SUI": ("Sui", "SUI"),
    "XRP": ("XRP", "Ripple"),
    "ADA": ("Cardano", "ADA"),
    "AVAX": ("Avalanche", "AVAX"),
    "LINK": ("Chainlink", "LINK"),
    "DOGE": ("Dogecoin", "DOGE"),
    "DOT": ("Polkadot", "DOT"),
    "LTC": ("Litecoin", "LTC"),
    "ATOM": ("Cosmos", "ATOM"),
    "NEAR": ("NEAR", "NEAR Protocol"),
    "ARB": ("Arbitrum", "ARB"),
    "APT": ("Aptos", "APT"),
    "TAO": ("Bittensor", "TAO"),
    "WIF": ("dogwifhat", "WIF"),
    "PEPE": ("Pepe", "PEPE"),
    "RENDER": ("Render", "RNDR"),
    "FET": ("Fetch.ai", "FET"),
    "SPY": ("SPY", "S&P 500"),
    "QQQ": ("QQQ", "Nasdaq"),
    "NVDA": ("NVIDIA", "NVDA"),
    "TSLA": ("Tesla", "TSLA"),
    "AAPL": ("Apple", "AAPL"),
    "MSFT": ("Microsoft", "MSFT"),
    "GOOGL": ("Google", "Alphabet", "GOOGL"),
    "META": ("Meta", "Facebook", "META"),
    "AMZN": ("Amazon", "AMZN"),
    "AMD": ("AMD", "Advanced Micro Devices"),
    "COIN": ("Coinbase", "COIN"),
    "MSTR": ("MicroStrategy", "MSTR"),
    "IBIT": ("IBIT", "Bitcoin ETF"),
}

_MEM_CACHE: TTLCache["RedditBuzzSnapshot | None"] = TTLCache(ttl_seconds=_CACHE_TTL)
_RATE_LOCK = Lock()
_LAST_REQUEST_AT = 0.0


@dataclass(frozen=True)
class RedditPostHit:
    title: str
    selftext: str
    score: int
    num_comments: int
    subreddit: str


@dataclass(frozen=True)
class RedditBuzzSnapshot:
    symbol: str
    query: str
    posts: tuple[RedditPostHit, ...]
    fetched_ok: bool
    source: str  # live | memory | disk | empty


def search_terms_for(symbol: str) -> list[str]:
    sym = symbol.upper().strip()
    aliases = list(_SYMBOL_ALIASES.get(sym, (sym,)))
    # Prefer cashtag-ish and $SYMBOL forms for equities
    terms = []
    for a in aliases:
        if a not in terms:
            terms.append(a)
    if f"${sym}" not in terms:
        terms.append(f"${sym}")
    return terms[:4]


def _subreddit_filter(symbol: str) -> str | None:
    asset = get_asset_class(symbol)
    if asset == AssetClass.CRYPTO:
        return "+".join(_CRYPTO_SUBS)
    return "+".join(_EQUITY_SUBS)


def _disk_path(symbol: str) -> Path:
    return _DISK_DIR / f"{symbol.upper()}.json"


def _user_agent() -> str:
    ua = settings.reddit_user_agent.strip()
    if ua:
        return ua
    return "signal-engine/1.0 (market research; contact: local)"


def _throttle() -> None:
    global _LAST_REQUEST_AT
    with _RATE_LOCK:
        now = time.monotonic()
        wait = _MIN_REQUEST_GAP - (now - _LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_AT = time.monotonic()


def _parse_listing(payload: object) -> list[RedditPostHit]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    children = data.get("children")
    if not isinstance(children, list):
        return []
    hits: list[RedditPostHit] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        post = child.get("data")
        if not isinstance(post, dict):
            continue
        title = str(post.get("title") or "")
        selftext = str(post.get("selftext") or "")
        try:
            score = int(post.get("score") or 0)
        except (TypeError, ValueError):
            score = 0
        try:
            comments = int(post.get("num_comments") or 0)
        except (TypeError, ValueError):
            comments = 0
        sub = str(post.get("subreddit") or "")
        if not title:
            continue
        hits.append(
            RedditPostHit(
                title=title,
                selftext=selftext[:500],
                score=score,
                num_comments=comments,
                subreddit=sub,
            )
        )
    return hits


def _snapshot_to_dict(snap: RedditBuzzSnapshot) -> dict:
    return {
        "symbol": snap.symbol,
        "query": snap.query,
        "fetched_ok": snap.fetched_ok,
        "source": snap.source,
        "posts": [asdict(p) for p in snap.posts],
    }


def _snapshot_from_dict(raw: object) -> RedditBuzzSnapshot | None:
    if not isinstance(raw, dict):
        return None
    try:
        posts_raw = raw.get("posts") or []
        posts: list[RedditPostHit] = []
        if isinstance(posts_raw, list):
            for p in posts_raw:
                if not isinstance(p, dict):
                    continue
                posts.append(
                    RedditPostHit(
                        title=str(p.get("title") or ""),
                        selftext=str(p.get("selftext") or ""),
                        score=int(p.get("score") or 0),
                        num_comments=int(p.get("num_comments") or 0),
                        subreddit=str(p.get("subreddit") or ""),
                    )
                )
        return RedditBuzzSnapshot(
            symbol=str(raw.get("symbol") or "").upper(),
            query=str(raw.get("query") or ""),
            posts=tuple(posts),
            fetched_ok=bool(raw.get("fetched_ok")),
            source=str(raw.get("source") or "disk"),
        )
    except Exception:
        logger.exception("Failed parsing reddit disk cache")
        return None


def _fetch_live(symbol: str) -> RedditBuzzSnapshot:
    sym = symbol.upper().strip()
    terms = search_terms_for(sym)
    # Primary query: first alias OR $SYMBOL
    query = " OR ".join(f'"{t}"' if " " in t else t for t in terms[:3])
    params: dict[str, str | int] = {
        "q": query,
        "sort": "new",
        "t": "day",
        "limit": 25,
        "type": "link",
        "restrict_sr": 1,
    }
    subs = _subreddit_filter(sym)
    url = f"{_SEARCH_BASE}/r/{subs}/search.json" if subs else f"{_SEARCH_BASE}/search.json"

    _throttle()
    headers = {"User-Agent": _user_agent()}
    try:
        with httpx.Client(timeout=10.0, headers=headers, follow_redirects=True) as client:
            resp = client.get(url, params=params)
            if resp.status_code in {403, 429, 503}:
                logger.warning("Reddit search soft-fail HTTP %s for %s", resp.status_code, sym)
                return RedditBuzzSnapshot(sym, query, (), False, "empty")
            resp.raise_for_status()
            hits = _parse_listing(resp.json())
        snap = RedditBuzzSnapshot(sym, query, tuple(hits), True, "live")
        disk_cache.write_json(_disk_path(sym), _snapshot_to_dict(snap))
        return snap
    except Exception:
        logger.warning("Reddit search failed for %s", sym, exc_info=True)
        return RedditBuzzSnapshot(sym, query, (), False, "empty")


def get_reddit_buzz(symbol: str, *, allow_live: bool = True) -> RedditBuzzSnapshot:
    """Return buzz snapshot: memory → disk → optional live fetch.

    When ``allow_live`` is False (cold ranking path), never hit Reddit —
    return stale/empty so ``rank_all`` stays fast.
    """
    sym = symbol.upper().strip()
    key = f"buzz:{sym}"

    cached = _MEM_CACHE.get(key, allow_stale=True)
    if cached is not None and (cached.fetched_ok or cached.posts):
        return RedditBuzzSnapshot(
            symbol=cached.symbol,
            query=cached.query,
            posts=cached.posts,
            fetched_ok=cached.fetched_ok,
            source="memory",
        )

    disk = _snapshot_from_dict(disk_cache.read_json(_disk_path(sym)))
    if disk is not None and (disk.posts or disk.fetched_ok):
        _MEM_CACHE.seed_stale(key, disk)
        return RedditBuzzSnapshot(
            symbol=disk.symbol,
            query=disk.query,
            posts=disk.posts,
            fetched_ok=disk.fetched_ok,
            source="disk",
        )

    if not allow_live or not settings.reddit_social_enabled:
        empty = RedditBuzzSnapshot(sym, "", (), False, "empty")
        return empty

    snap = _fetch_live(sym)
    _MEM_CACHE.seed_stale(key, snap)
    return snap


def prefetch_reddit_buzz(symbols: list[str]) -> dict[str, int | str]:
    """Warm Reddit caches for tracked symbols (scheduled / Celery)."""
    if not settings.reddit_social_enabled:
        return {"status": "disabled", "warmed": 0}

    warmed = 0
    errors = 0
    for symbol in symbols:
        try:
            snap = get_reddit_buzz(symbol, allow_live=True)
            if snap.fetched_ok:
                warmed += 1
            elif not snap.posts:
                errors += 1
        except Exception:
            errors += 1
            logger.exception("Reddit prefetch failed for %s", symbol)
    return {"status": "ok", "warmed": warmed, "errors": errors, "symbols": len(symbols)}
