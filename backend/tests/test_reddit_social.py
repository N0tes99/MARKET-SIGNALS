"""Reddit public buzz + social confirmation scoring."""

from __future__ import annotations

from app.engines.sentiment_engine.reddit_social import score_reddit_buzz
from app.market_data.providers.reddit_public import RedditBuzzSnapshot, RedditPostHit


def _snap(*titles: str, scores: list[int] | None = None) -> RedditBuzzSnapshot:
    posts = []
    for i, title in enumerate(titles):
        sc = (scores[i] if scores and i < len(scores) else 10)
        posts.append(
            RedditPostHit(
                title=title,
                selftext="",
                score=sc,
                num_comments=5,
                subreddit="stocks",
            )
        )
    return RedditBuzzSnapshot(
        symbol="NVDA",
        query="NVDA",
        posts=tuple(posts),
        fetched_ok=True,
        source="test",
    )


def test_quiet_is_neutral() -> None:
    empty = RedditBuzzSnapshot("BTC", "", (), False, "empty")
    result = score_reddit_buzz(empty)
    assert result.score == 50.0
    assert result.available is False


def test_crowded_bullish_is_caution() -> None:
    snap = _snap(
        "NVDA to the moon breakout bullish calls",
        "NVIDIA moon rally squeeze long",
        "NVDA bull run buy the dip",
        "calls calls breakout moon",
        "bullish moon squeeze",
        "rally breakout long",
        "moon moon moon",
        "bullish breakout",
        "calls squeeze",
        "to the moon",
        "bullish rally",
        "breakout moon",
        scores=[100] * 12,
    )
    result = score_reddit_buzz(snap)
    assert result.available is True
    assert result.score < 50
    assert "caution" in result.description or "bullish" in result.description


def test_fearful_chatter_is_supportive() -> None:
    snap = _snap(
        "NVDA crash dump bearish puts",
        "NVIDIA bubble scam dump rekt",
        "NVDA selloff overvalued short",
        "crash bagholder dump",
        "bearish puts dump",
        "overvalued bubble",
        scores=[80] * 6,
    )
    result = score_reddit_buzz(snap)
    assert result.available is True
    assert result.score > 50


def test_sentiment_engine_splits_weights(monkeypatch) -> None:
    from app.engines.sentiment_engine.engine import SentimentEngine
    from app.engines.sentiment_engine.reddit_social import RedditSocialResult
    from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory

    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.fetch_fear_greed",
        lambda: (50, "Neutral"),
    )
    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.settings.reddit_social_enabled",
        True,
    )
    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.analyze_reddit_social",
        lambda symbol, allow_live=False: RedditSocialResult(
            score=42.0,
            description="Reddit: elevated bullish chatter (4 posts, eng 40, lean +0.50)",
            mention_count=4,
            engagement=40,
            lean=0.5,
            available=True,
        ),
    )

    items = SentimentEngine().contribute_evidence("NVDA")
    assert len(items) == 2
    assert items[0].source == "sentiment_engine"
    assert items[1].source == "reddit_social"
    total_w = sum(i.weight for i in items)
    assert abs(total_w - DEFAULT_WEIGHTS[ScoringCategory.SENTIMENT]) < 0.05


def test_sentiment_engine_full_weight_without_reddit(monkeypatch) -> None:
    from app.engines.sentiment_engine.engine import SentimentEngine
    from app.scoring.weights import DEFAULT_WEIGHTS, ScoringCategory

    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.fetch_fear_greed",
        lambda: (25, "Fear"),
    )
    monkeypatch.setattr(
        "app.engines.sentiment_engine.engine.settings.reddit_social_enabled",
        False,
    )
    items = SentimentEngine().contribute_evidence("BTC")
    assert len(items) == 1
    assert items[0].weight == DEFAULT_WEIGHTS[ScoringCategory.SENTIMENT]


def test_get_reddit_buzz_cache_only(monkeypatch) -> None:
    from app.market_data.providers import reddit_public as rp

    monkeypatch.setattr(rp.settings, "reddit_social_enabled", True)
    rp._MEM_CACHE.clear()

    called = {"n": 0}

    def boom(symbol: str) -> rp.RedditBuzzSnapshot:
        called["n"] += 1
        raise AssertionError("live fetch should not run")

    monkeypatch.setattr(rp, "_fetch_live", boom)
    monkeypatch.setattr(rp, "_snapshot_from_dict", lambda raw: None)
    monkeypatch.setattr(rp.disk_cache, "read_json", lambda path: None)

    snap = rp.get_reddit_buzz("ETH", allow_live=False)
    assert snap.source == "empty"
    assert called["n"] == 0
