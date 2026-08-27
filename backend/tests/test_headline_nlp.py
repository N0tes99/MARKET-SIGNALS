"""Headline NLP v0 — RSS titles, keyword polarity, cortex-only."""

from app.cortex.specialists import collect_news_opinion
from app.engines.event_engine.engine import EventSnapshot
from app.engines.news_nlp.headlines import parse_rss_titles, score_titles, yahoo_rss_symbol


def test_yahoo_rss_symbol_maps_crypto() -> None:
    assert yahoo_rss_symbol("BTC") == "BTC-USD"
    assert yahoo_rss_symbol("AAPL") == "AAPL"


def test_parse_rss_titles() -> None:
    xml = """
    <rss><channel>
      <item><title>Bitcoin ETF inflow hits record</title></item>
      <item><title>SEC charges exchange</title></item>
    </channel></rss>
    """
    titles = parse_rss_titles(xml)
    assert titles[0].startswith("Bitcoin")
    assert "SEC" in titles[1]


def test_score_titles_is_directional() -> None:
    up, direction = score_titles(["SOL rally hits record on ETF inflow"])
    assert direction == "up"
    assert up > 50
    down, bear = score_titles(["Exchange hack and SEC charges spark crash"])
    assert bear == "down"
    assert down < 50


def test_news_opinion_blends_headlines(monkeypatch) -> None:
    from app.engines.news_nlp.headlines import HeadlineBundle

    monkeypatch.setattr(
        "app.cortex.specialists.fetch_headline_bundle",
        lambda _symbol: HeadlineBundle(
            score=80.0,
            direction="up",
            titles=["SOL rally hits record"],
            source="yahoo-rss",
        ),
    )

    class _News:
        def snapshot(self, symbol: str, *, include_earnings: bool = False) -> EventSnapshot:
            del symbol, include_earnings
            return EventSnapshot(
                events=["CPI in 5d"],
                nearest_days=5.0,
                score=50.0,
                description="Events: quiet",
            )

    op = collect_news_opinion(_News(), "SOL")  # type: ignore[arg-type]
    assert op.metadata["headline_score"] == 80.0
    assert any("Headline:" in line for line in op.factors)
    assert op.score == 59.0
    assert op.direction == "up"
