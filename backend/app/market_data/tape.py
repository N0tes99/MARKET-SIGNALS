"""Public-trade tape CVD (Kraken spot trades; Binance when enabled).

This is cumulative volume delta from recent prints, not perp liquidation tape
and not an OHLCV buying-pressure proxy.
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import UTC, datetime

from app.config import settings
from app.market_data.providers.binance import use_binance
from app.market_data.symbols import to_binance_symbol, to_kraken_pair
from app.utils.http_client import shared_client
from app.utils.ttl_cache import TTLCache

logger = logging.getLogger(__name__)

_MIN_TRADES = 30


@dataclass(frozen=True)
class TapeTrade:
    price: float
    volume: float
    ts: datetime
    side: str  # buy | sell


@dataclass(frozen=True)
class TapeCvd:
    symbol: str
    source: str
    buy_volume: float
    sell_volume: float
    delta: float
    score: float
    trade_count: int
    as_of: datetime

    @property
    def direction(self) -> str | None:
        if self.score >= 58:
            return "up"
        if self.score <= 42:
            return "down"
        return None


_TAPE_CACHE: TTLCache[TapeCvd] = TTLCache(ttl_seconds=45.0)


def _score_from_volumes(buy: float, sell: float) -> float:
    total = buy + sell
    if total <= 0:
        return 50.0
    imbalance = (buy - sell) / total
    return round(50.0 + 50.0 * math.tanh(imbalance * 1.5), 2)


def compute_tape_cvd(trades: list[TapeTrade], *, symbol: str, source: str) -> TapeCvd | None:
    """Aggregate taker buy/sell volume into a 0–100 CVD score."""
    if len(trades) < _MIN_TRADES:
        return None
    buy = sum(t.volume * t.price for t in trades if t.side == "buy")
    sell = sum(t.volume * t.price for t in trades if t.side == "sell")
    last_ts = max((t.ts for t in trades), default=datetime.now(UTC))
    return TapeCvd(
        symbol=symbol.upper(),
        source=source,
        buy_volume=buy,
        sell_volume=sell,
        delta=buy - sell,
        score=_score_from_volumes(buy, sell),
        trade_count=len(trades),
        as_of=last_ts,
    )


def _kraken_trades(symbol: str) -> list[TapeTrade]:
    pair = to_kraken_pair(symbol)
    url = f"{settings.kraken_api_url}/0/public/Trades"
    client = shared_client(timeout=3.0, name="kraken-tape")
    response = client.get(url, params={"pair": pair})
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise RuntimeError(f"Kraken trades error: {payload['error']}")
    result_key = next(k for k in payload["result"] if k != "last")
    rows = payload["result"][result_key][-200:]
    trades: list[TapeTrade] = []
    for row in rows:
        side = "buy" if row[3] == "b" else "sell"
        trades.append(
            TapeTrade(
                price=float(row[0]),
                volume=float(row[1]),
                ts=datetime.fromtimestamp(float(row[2]), tz=UTC),
                side=side,
            )
        )
    return trades


def _binance_trades(symbol: str) -> list[TapeTrade]:
    pair = to_binance_symbol(symbol)
    url = f"{settings.binance_spot_url}/api/v3/aggTrades"
    client = shared_client(timeout=3.0, name="binance-tape")
    response = client.get(url, params={"symbol": pair, "limit": 200})
    response.raise_for_status()
    trades: list[TapeTrade] = []
    for row in response.json():
        # isBuyerMaker True → taker sold
        side = "sell" if row.get("m") else "buy"
        trades.append(
            TapeTrade(
                price=float(row["p"]),
                volume=float(row["q"]),
                ts=datetime.fromtimestamp(int(row["T"]) / 1000, tz=UTC),
                side=side,
            )
        )
    return trades


def fetch_tape_cvd(symbol: str) -> TapeCvd | None:
    """Kraken first (Render-safe); Binance only when enabled."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    cache_key = f"tape:{symbol.upper()}"
    cached = _TAPE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    cvd: TapeCvd | None = None
    try:
        cvd = compute_tape_cvd(_kraken_trades(symbol), symbol=symbol, source="kraken_tape")
    except Exception:
        logger.debug("Kraken tape CVD failed for %s", symbol, exc_info=True)
    if cvd is None and use_binance():
        try:
            cvd = compute_tape_cvd(
                _binance_trades(symbol), symbol=symbol, source="binance_tape"
            )
        except Exception:
            logger.debug("Binance tape CVD failed for %s", symbol, exc_info=True)
    if cvd is not None:
        _TAPE_CACHE.set(cache_key, cvd)
    return cvd
