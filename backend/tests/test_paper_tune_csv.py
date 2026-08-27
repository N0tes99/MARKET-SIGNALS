"""Paper-bot tuning CSV uses the requested column layout."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.service_dependencies import get_paper_agent
from app.engines.paper_agent.tune_csv import (
    CSV_COLUMNS,
    market_condition,
    paper_trades_to_csv,
    user_feedback,
)
from app.engines.paper_agent.types import PaperTrade
from app.main import app


def _trade(**overrides: object) -> PaperTrade:
    now = datetime(2026, 8, 26, 14, 30, tzinfo=UTC)
    payload: dict[str, object] = {
        "id": str(uuid4()),
        "symbol": "BTC",
        "source": "crypto_perp_v2",
        "setup_type": "perp_momentum",
        "direction": "long",
        "fingerprint": "fp",
        "signal_at": now,
        "confidence": 72.0,
        "opportunity_score": 80.0,
        "size_usd": 2500.0,
        "status": "closed",
        "optimistic_entry": 65000.0,
        "optimistic_entry_at": now,
        "optimistic_exit": 68000.0,
        "optimistic_return_pct": 4.6,
        "honest_entry": 65100.0,
        "honest_entry_at": now,
        "honest_exit": 67990.0,
        "honest_return_pct": 4.4,
        "factors": ["Funding +12.00 bps", "Greed zone soft-conflicts long"],
        "notes": "F&G 78 (Greed)",
        "closed_at": now,
    }
    payload.update(overrides)
    return PaperTrade(**payload)  # type: ignore[arg-type]


def test_csv_columns_and_honest_ledger() -> None:
    text = paper_trades_to_csv([_trade()])
    header, row = text.strip().split("\n")
    assert header.split(",") == list(CSV_COLUMNS)
    assert "2026-08-26 14:30" in row
    assert "BTC" in row
    assert "65100.00" in row
    assert "67990.00" in row
    assert "4.4%" in row
    assert "perp_momentum" in row
    assert "Greed_Trend_Bullish" in row
    assert "Confident" in row
    assert "65000.00" not in row  # optimistic entry must not replace honest


def test_open_trade_leaves_exit_blank_and_marks_unrealized() -> None:
    trade = _trade(
        status="open",
        honest_exit=None,
        optimistic_exit=None,
        honest_return_pct=None,
        optimistic_return_pct=None,
        mark_price=66000.0,
        factors=["Fear zone soft-supports long"],
        notes="",
        confidence=58.0,
        setup_type="liq_flush",
        direction="long",
    )
    text = paper_trades_to_csv([trade])
    row = text.strip().split("\n")[1]
    parts = row.split(",")
    assert parts[3] == ""  # exit_price
    assert parts[4].endswith("%")
    assert parts[5] == "liq_flush"
    assert market_condition(trade) == "Fear_High_Vol_Bullish"
    assert user_feedback(58.0) == "Hesitant"


def test_short_liq_is_high_vol_bearish() -> None:
    trade = _trade(direction="short", setup_type="liq_flush", factors=["OI unwinding"], notes="")
    assert market_condition(trade) == "High_Vol_Bearish"


class _StubAgent:
    def all_trades(self):
        return [_trade()]


@pytest.mark.asyncio
async def test_trades_csv_endpoint() -> None:
    app.dependency_overrides[get_paper_agent] = lambda: _StubAgent()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/paper/trades.csv")
    app.dependency_overrides.pop(get_paper_agent, None)
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "paper-trades-" in res.headers.get("content-disposition", "")
    assert res.text.split("\n")[0].startswith("timestamp,asset_symbol")
    assert "BTC" in res.text
