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

# Circuit breaker: after repeated block responses, stop live fetches for a while.
# Datacenter egress (e.g. Render) often gets HTTP 403 on unauthenticated public JSON.
_BLOCK_STATUSES = frozenset({403, 429, 503})
_BLOCK_OPEN_THRESHOLD = 3
_CIRCUIT_COOLDOWN_SEC = 1_800.0  # 30 minutes
_BLOCK_LOG_COOLDOWN_SEC = 300.0  # warn at most once per 5 minutes

# Reddit-preferred UA shape: <platform>:<app ID>:<version> (contact)
_DEFAULT_USER_AGENT = (
    "web:signal-engine:v1.1.0 (research; +https://github.com/N0tes99/MARKET-SIGNALS)"
)

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

_CIRCUIT_LOCK = Lock()
_CIRCUIT_OPEN_UNTIL = 0.0
_CONSECUTIVE_BLOCKS = 0
_LAST_BLOCK_LOG_AT = 0.0
_SUPPRESSED_BLOCK_LOGS = 0


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
    source: str  # live | memory | disk | empty | circuit_open


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
    return _DEFAULT_USER_AGENT


def _request_headers() -> dict[str, str]:
    """Headers Reddit expects for public JSON (unique UA + browser-ish Accept)."""
    return {
        "User-Agent": _user_agent(),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _throttle() -> None:
    global _LAST_REQUEST_AT
    with _RATE_LOCK:
        now = time.monotonic()
        wait = _MIN_REQUEST_GAP - (now - _LAST_REQUEST_AT)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_AT = time.monotonic()


def reset_circuit_state() -> None:
    """Clear breaker state (tests / manual recovery)."""
    global _CIRCUIT_OPEN_UNTIL, _CONSECUTIVE_BLOCKS, _LAST_BLOCK_LOG_AT, _SUPPRESSED_BLOCK_LOGS
    with _CIRCUIT_LOCK:
        _CIRCUIT_OPEN_UNTIL = 0.0
        _CONSECUTIVE_BLOCKS = 0
        _LAST_BLOCK_LOG_AT = 0.0
        _SUPPRESSED_BLOCK_LOGS = 0


def circuit_is_open() -> bool:
    """True when live Reddit fetches are paused after repeated blocks."""
    with _CIRCUIT_LOCK:
        return time.monotonic() < _CIRCUIT_OPEN_UNTIL


def _note_success() -> None:
    global _CONSECUTIVE_BLOCKS
    with _CIRCUIT_LOCK:
        _CONSECUTIVE_BLOCKS = 0


def _note_block(status: int, symbol: str) -> None:
    """Record a block response; open circuit and rate-limit warnings."""
    global _CIRCUIT_OPEN_UNTIL, _CONSECUTIVE_BLOCKS, _LAST_BLOCK_LOG_AT, _SUPPRESSED_BLOCK_LOGS
    with _CIRCUIT_LOCK:
        _CONSECUTIVE_BLOCKS += 1
        now = time.monotonic()
        opened = False
        if _CONSECUTIVE_BLOCKS >= _BLOCK_OPEN_THRESHOLD:
            _CIRCUIT_OPEN_UNTIL = now + _CIRCUIT_COOLDOWN_SEC
            opened = True

        if now - _LAST_BLOCK_LOG_AT < _BLOCK_LOG_COOLDOWN_SEC:
            _SUPPRESSED_BLOCK_LOGS += 1
            return

        suppressed = _SUPPRESSED_BLOCK_LOGS
        _SUPPRESSED_BLOCK_LOGS = 0
        _LAST_BLOCK_LOG_AT = now

    extra = f" (+{suppressed} similar suppressed)" if suppressed else ""
    if opened:
        logger.warning(
            "Reddit search blocked (HTTP %s for %s)%s; pausing live fetches for %.0fs. "
            "Datacenter IPs (e.g. Render) often get 403 on public JSON — sentiment "
            "continues without Reddit. Set REDDIT_SOCIAL_ENABLED=false to disable, or "
            "REDDIT_USER_AGENT to Reddit's platform:app:version format.",
            status,
            symbol,
            extra,
            _CIRCUIT_COOLDOWN_SEC,
        )
    else:
        logger.warning(
            "Reddit search soft-fail HTTP %s for %s%s",
            status,
            symbol,
            extra,
        )


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


def _empty_snap(sym: str, query: str = "", *, source: str = "empty") -> RedditBuzzSnapshot:
    return RedditBuzzSnapshot(sym, query, (), False, source)


def _fetch_live(symbol: str) -> RedditBuzzSnapshot:
    sym = symbol.upper().strip()
    terms = search_terms_for(sym)
    # Primary query: first alias OR $SYMBOL
    query = " OR ".join(f'"{t}"' if " " in t else t for t in terms[:3])

    if circuit_is_open():
        return _empty_snap(sym, query, source="circuit_open")

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
    try:
        with httpx.Client(timeout=10.0, headers=_request_headers(), follow_redirects=True) as client:
            resp = client.get(url, params=params)
            if resp.status_code in _BLOCK_STATUSES:
                _note_block(resp.status_code, sym)
                return _empty_snap(sym, query)
            resp.raise_for_status()
            hits = _parse_listing(resp.json())
        _note_success()
        snap = RedditBuzzSnapshot(sym, query, tuple(hits), True, "live")
        disk_cache.write_json(_disk_path(sym), _snapshot_to_dict(snap))
        return snap
    except Exception:
        logger.warning("Reddit search failed for %s", sym, exc_info=True)
        return _empty_snap(sym, query)


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
        return _empty_snap(sym)

    if circuit_is_open():
        return _empty_snap(sym, source="circuit_open")

    snap = _fetch_live(sym)
    _MEM_CACHE.seed_stale(key, snap)
    return snap


def prefetch_reddit_buzz(symbols: list[str]) -> dict[str, int | str]:
    """Warm Reddit caches for tracked symbols (scheduled / Celery)."""
    if not settings.reddit_social_enabled:
        return {"status": "disabled", "warmed": 0}

    if circuit_is_open():
        return {
            "status": "circuit_open",
            "warmed": 0,
            "errors": 0,
            "symbols": len(symbols),
        }

    warmed = 0
    errors = 0
    skipped = 0
    for i, symbol in enumerate(symbols):
        if circuit_is_open():
            skipped = len(symbols) - i
            break
        try:
            snap = get_reddit_buzz(symbol, allow_live=True)
            if snap.fetched_ok:
                warmed += 1
            elif snap.source == "circuit_open":
                skipped = len(symbols) - i
                break
            elif not snap.posts:
                errors += 1
        except Exception:
            errors += 1
            logger.exception("Reddit prefetch failed for %s", symbol)
    status = "circuit_open" if skipped and warmed == 0 else "ok"
    return {
        "status": status,
        "warmed": warmed,
        "errors": errors,
        "skipped": skipped,
        "symbols": len(symbols),
    }
