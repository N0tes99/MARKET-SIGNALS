"""Paper open confirmation: grade, Fear & Greed, risk/R:R."""

from types import SimpleNamespace

from app.engines.paper_agent.confirm import confirm_open, grade_meets_floor


def test_grade_floor() -> None:
    assert grade_meets_floor("B")
    assert grade_meets_floor("A")
    assert grade_meets_floor("A+")
    assert not grade_meets_floor("C")
    assert not grade_meets_floor("D")


def test_confirm_off_without_pipeline() -> None:
    skip, tp, sl, note = confirm_open(
        symbol="BTC",
        direction="long",
        pipeline=None,
        entry_price=65000.0,
    )
    assert skip is None
    assert tp == 6.0
    assert sl == 3.0
    assert note == "confirm:off"


def test_confirm_skips_when_fng_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: None,
    )
    skip, _, _, _ = confirm_open(
        symbol="BTC",
        direction="long",
        pipeline=SimpleNamespace(),
        entry_price=100.0,
    )
    assert skip == "skip:fng_unavailable"


def test_confirm_blocks_long_in_extreme_greed(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (82, "Extreme Greed"),
    )
    skip, _, _, note = confirm_open(
        symbol="BTC",
        direction="long",
        pipeline=SimpleNamespace(),
        entry_price=100.0,
    )
    assert skip == "skip:fng_greed"
    assert "82" in note


def test_confirm_blocks_short_in_extreme_fear(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (12, "Extreme Fear"),
    )
    skip, _, _, _ = confirm_open(
        symbol="BTC",
        direction="short",
        pipeline=SimpleNamespace(),
        entry_price=100.0,
    )
    assert skip == "skip:fng_fear"


def test_confirm_skips_grade_c(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )

    class _Pipe:
        def evaluate(self, symbol, timeframe="1h"):
            return SimpleNamespace(
                opportunity=SimpleNamespace(trade_grade="C"),
                risk=SimpleNamespace(score=70.0, risk_reward_ratio=2.0),
            )

    skip, _, _, note = confirm_open(
        symbol="BTC",
        direction="long",
        pipeline=_Pipe(),
        entry_price=100.0,
    )
    assert skip == "skip:grade:C"
    assert "C" in note


def test_confirm_skips_weak_risk(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (45, "Neutral"),
    )

    class _Pipe:
        def evaluate(self, symbol, timeframe="1h"):
            return SimpleNamespace(
                opportunity=SimpleNamespace(trade_grade="B"),
                risk=SimpleNamespace(
                    score=40.0,
                    risk_reward_ratio=1.1,
                    stop_loss=97,
                    take_profit=106,
                ),
            )

    skip, _, _, _ = confirm_open(
        symbol="ETH",
        direction="long",
        pipeline=_Pipe(),
        entry_price=100.0,
    )
    assert skip == "skip:risk"


def test_confirm_uses_atr_exit_pcts(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.engines.paper_agent.confirm.fetch_fear_greed",
        lambda: (40, "Fear"),
    )

    class _Pipe:
        def evaluate(self, symbol, timeframe="1h"):
            return SimpleNamespace(
                opportunity=SimpleNamespace(trade_grade="A"),
                risk=SimpleNamespace(
                    score=62.0,
                    risk_reward_ratio=2.0,
                    stop_loss=96.0,
                    take_profit=108.0,
                ),
            )

    skip, tp, sl, note = confirm_open(
        symbol="BTC",
        direction="long",
        pipeline=_Pipe(),
        entry_price=100.0,
    )
    assert skip is None
    assert abs(sl - 4.0) < 0.01
    assert abs(tp - 8.0) < 0.01
    assert "grade A" in note
    assert "ATR" in note
