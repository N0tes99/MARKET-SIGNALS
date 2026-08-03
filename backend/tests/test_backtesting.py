"""Backtesting runner tests."""

from app.backtesting import BacktestRunner
from app.market_data.providers.mock import MockMarketDataProvider
from app.market_data.service import MarketDataService


def test_backtest_runner_returns_metrics() -> None:
    md = MarketDataService(provider=MockMarketDataProvider())
    runner = BacktestRunner(market_data=md)
    result = runner.run("BTC", timeframe="1h", hold_bars=12, signal_threshold=50.0)

    assert result.symbol == "BTC"
    assert result.total_signals >= 0
    assert 0.0 <= result.win_rate <= 100.0
