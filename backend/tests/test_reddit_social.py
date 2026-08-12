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
    rp.reset_circuit_state()

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


def test_request_headers_include_accept(monkeypatch) -> None:
    from app.market_data.providers import reddit_public as rp

    monkeypatch.setattr(rp.settings, "reddit_user_agent", "")
    headers = rp._request_headers()
    assert headers["Accept"] == "application/json"
    assert "Accept-Language" in headers
    assert headers["User-Agent"].startswith("web:signal-engine:")


def test_circuit_opens_after_repeated_403(monkeypatch) -> None:
    from app.market_data.providers import reddit_public as rp

    rp.reset_circuit_state()
    rp.reset_oauth_token()
    monkeypatch.setattr(rp, "_throttle", lambda: None)
    monkeypatch.setattr(rp.settings, "reddit_social_enabled", True)
    monkeypatch.setattr(rp.settings, "reddit_client_id", "")
    monkeypatch.setattr(rp.settings, "reddit_client_secret", "")
    monkeypatch.setattr(rp, "_BLOCK_LOG_COOLDOWN_SEC", 0.0)

    class _Resp:
        def __init__(self, code: int) -> None:
            self.status_code = code

        def raise_for_status(self) -> None:
            raise AssertionError("should not raise for block status")

        def json(self) -> dict:
            return {}

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *args) -> None:
            return None

        def get(self, url, params=None) -> _Resp:
            return _Resp(403)

    monkeypatch.setattr(rp.httpx, "Client", _Client)

    for sym in ("SMH", "IBIT", "XLE"):
        snap = rp._fetch_live(sym)
        assert snap.fetched_ok is False
        assert snap.source == "empty"

    assert rp.circuit_is_open()
    blocked = rp._fetch_live("AAPL")
    assert blocked.source == "circuit_open"

    result = rp.prefetch_reddit_buzz(["NVDA", "MSFT", "GOOGL"])
    assert result["status"] == "circuit_open"
    assert result["warmed"] == 0


def test_block_warnings_are_rate_limited(monkeypatch, caplog) -> None:
    import logging

    from app.market_data.providers import reddit_public as rp

    rp.reset_circuit_state()
    monkeypatch.setattr(rp, "_BLOCK_OPEN_THRESHOLD", 99)
    monkeypatch.setattr(rp, "_BLOCK_LOG_COOLDOWN_SEC", 60.0)

    with caplog.at_level(logging.WARNING, logger=rp.logger.name):
        rp._note_block(403, "SMH")
        rp._note_block(403, "IBIT")
        rp._note_block(403, "XLE")

    soft = [r for r in caplog.records if "soft-fail HTTP 403" in r.getMessage()]
    assert len(soft) == 1
    assert "SMH" in soft[0].getMessage()
    assert rp._SUPPRESSED_BLOCK_LOGS == 2


def test_oauth_search_uses_bearer_and_oauth_host(monkeypatch) -> None:
    from app.market_data.providers import reddit_public as rp

    rp.reset_circuit_state()
    rp.reset_oauth_token()
    monkeypatch.setattr(rp, "_throttle", lambda: None)
    monkeypatch.setattr(rp.settings, "reddit_client_id", "abc123")
    monkeypatch.setattr(rp.settings, "reddit_client_secret", "s3cret")
    monkeypatch.setattr(rp.disk_cache, "write_json", lambda *args, **kwargs: None)

    seen: dict[str, object] = {}

    class _TokenResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"access_token": "tok_live", "expires_in": 3600}

    class _SearchResp:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "data": {
                    "children": [
                        {
                            "data": {
                                "title": "NVDA breakout",
                                "selftext": "",
                                "score": 12,
                                "num_comments": 3,
                                "subreddit": "stocks",
                            }
                        }
                    ]
                }
            }

    class _Client:
        def __init__(self, *args, **kwargs) -> None:
            seen["headers"] = kwargs.get("headers") or {}

        def __enter__(self) -> _Client:
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url, auth=None, data=None) -> _TokenResp:
            seen["token_url"] = url
            seen["auth"] = auth
            seen["grant"] = data
            return _TokenResp()

        def get(self, url, params=None) -> _SearchResp:
            seen["search_url"] = url
            seen["params"] = params
            return _SearchResp()

    monkeypatch.setattr(rp.httpx, "Client", _Client)

    snap = rp._fetch_live("NVDA")
    assert snap.fetched_ok is True
    assert snap.posts[0].title == "NVDA breakout"
    assert seen["token_url"] == rp._TOKEN_URL
    assert seen["auth"] == ("abc123", "s3cret")
    assert seen["grant"] == {"grant_type": "client_credentials"}
    assert str(seen["search_url"]).startswith("https://oauth.reddit.com/")
    assert ".json" not in str(seen["search_url"])
    assert seen["headers"].get("Authorization") == "Bearer tok_live"

    # Cached token — second call should not post again.
    seen.pop("token_url", None)
    snap2 = rp._fetch_live("NVDA")
    assert snap2.fetched_ok is True
    assert "token_url" not in seen


def test_installed_app_uses_device_grant(monkeypatch) -> None:
    from app.market_data.providers import reddit_public as rp

    rp.reset_oauth_token()
    monkeypatch.setattr(rp.settings, "reddit_client_id", "installedid")
    monkeypatch.setattr(rp.settings, "reddit_client_secret", "")
    form = rp._token_form()
    assert form["grant_type"] == rp._INSTALLED_GRANT
    assert form["device_id"] == "signal-engine-render"
    assert rp.oauth_configured() is True
