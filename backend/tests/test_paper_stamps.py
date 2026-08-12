"""Paper desk stamp mint + Discord ping."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd

from app.engines.paper_agent.agent import PaperAgent
from app.engines.paper_agent.stamp_art import render_stamp_png
from app.engines.paper_agent.stamps import mint_stamp, paper_discord_payload
from app.engines.paper_agent.store import PaperTradeStore
from app.engines.paper_agent.types import PaperTrade


def test_stamp_is_seeded() -> None:
    a = mint_stamp("trade-aaa")
    b = mint_stamp("trade-aaa")
    c = mint_stamp("trade-bbb")
    assert a == b
    assert a.serial == b.serial
    assert a.line == b.line
    assert c.serial != a.serial
    assert a.rarity in {"Common", "Uncommon", "Rare", "Holo", "Mythic"}
    assert a.serial.startswith("SE-")
    assert len(a.line) <= 160
    png_a = render_stamp_png(a, symbol="BTC", direction="short", kind="open")
    png_b = render_stamp_png(b, symbol="BTC", direction="short", kind="open")
    png_c = render_stamp_png(c, symbol="ETH", direction="long", kind="open")
    assert png_a == png_b
    assert png_a != png_c
    assert png_a.startswith(b"\x89PNG")


def test_paper_embed_open_and_close() -> None:
    stamp = mint_stamp("embed-1")
    now = datetime.now(UTC)
    trade = PaperTrade(
        id="embed-1",
        symbol="BTC",
        source="crypto_setup",
        setup_type="funding_extreme",
        direction="short",
        fingerprint="fp",
        signal_at=now,
        confidence=72.0,
        opportunity_score=72.0,
        size_usd=2500.0,
        status="open",
        optimistic_entry=65000.0,
        optimistic_entry_at=now,
        take_profit_pct=8.0,
        stop_loss_pct=4.0,
        stamp=stamp.line,
    )
    content, embed, png = paper_discord_payload("open", trade, stamp)
    assert "PAPER OPEN" in content
    assert stamp.title in content
    assert embed["fields"][0]["value"] == "SHORT BTC"
    assert embed["image"]["url"] == "attachment://paper-stamp.png"
    assert png.startswith(b"\x89PNG")

    trade.status = "closed"
    trade.honest_pnl_usd = -75.0
    trade.honest_return_pct = -3.0
    trade.close_reason = "stop_loss_-4.0%"
    content2, embed2, png2 = paper_discord_payload("close", trade, stamp)
    assert png2.startswith(b"\x89PNG")
    assert "VOIDED" in content2
    assert "stop_loss" in embed2["fields"][0]["value"]


def test_agent_stamps_and_pings_discord(monkeypatch) -> None:
    store = PaperTradeStore()
    signal_at = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    sent: list[tuple[str, str]] = []

    class _Alerts:
        def discord_configured(self) -> bool:
            return True

        def send_embed(self, symbol, embed, *, content=None, username="Signal Engine", **kwargs):
            sent.append((symbol, content or ""))
            return True

    class _Crypto:
        def scan_feed(self, *args, **kwargs):
            return [
                SimpleNamespace(
                    symbol="BTC",
                    setup_type="funding_extreme",
                    direction_bias="short",
                    confidence=70.0,
                    factors=["funding elevated"],
                )
            ]

    class _Equity:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=65000.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame(
                [
                    {
                        "timestamp": signal_at + timedelta(minutes=15),
                        "open": 64900.0,
                        "high": 65000.0,
                        "low": 64800.0,
                        "close": 64950.0,
                        "volume": 10.0,
                    }
                ]
            )

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Crypto(),  # type: ignore[arg-type]
        equity_scanner=_Equity(),  # type: ignore[arg-type]
        store=store,
        alerts=_Alerts(),
        size_usd=2500.0,
    )

    class _DT:
        @staticmethod
        def now(tz=None):
            return signal_at

    monkeypatch.setattr("app.engines.paper_agent.agent.datetime", _DT)
    notes = agent.tick()
    assert any(n.startswith("open:BTC") for n in notes)
    trade = store.list_all()[0]
    assert trade.stamp
    assert trade.stamp.startswith(mint_stamp(trade.id).emoji)
    assert sent and sent[0][0] == "BTC"
    assert "PAPER OPEN" in sent[0][1]


def test_close_pings_discord(monkeypatch) -> None:
    store = PaperTradeStore()
    opened = datetime(2026, 8, 10, 15, 0, tzinfo=UTC)
    trade_id = str(uuid4())
    store.upsert(
        PaperTrade(
            id=trade_id,
            symbol="ETH",
            source="crypto_setup",
            setup_type="funding_extreme",
            direction="long",
            fingerprint="eth-fp",
            signal_at=opened,
            confidence=70.0,
            opportunity_score=70.0,
            size_usd=2500.0,
            status="open",
            optimistic_entry=100.0,
            optimistic_entry_at=opened,
            honest_entry=100.0,
            honest_entry_at=opened,
            mark_price=100.0,
            stamp=mint_stamp(trade_id).line,
        )
    )
    sent: list[str] = []

    class _Alerts:
        def discord_configured(self) -> bool:
            return True

        def send_embed(self, symbol, embed, *, content=None, username="Signal Engine", **kwargs):
            sent.append(content or "")
            return True

    class _Empty:
        def scan_feed(self, *args, **kwargs):
            return []

    class _Market:
        def get_ticker(self, symbol):
            return SimpleNamespace(price=109.0)

        def safe_get_ohlcv(self, symbol, timeframe, limit=96):
            return pd.DataFrame()

    agent = PaperAgent(
        market_data=_Market(),  # type: ignore[arg-type]
        crypto_scanner=_Empty(),  # type: ignore[arg-type]
        equity_scanner=_Empty(),  # type: ignore[arg-type]
        store=store,
        alerts=_Alerts(),
    )
    agent._last_discover_at = opened
    monkeypatch.setattr(
        "app.engines.paper_agent.agent.should_close",
        lambda **kwargs: "take_profit_+8.0%",
    )
    agent.tick()
    assert any("VOIDED" in c or "CLEARED" in c for c in sent)
