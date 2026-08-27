"""Parquet lake dump — refuses empty warehouse and disabled path."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.data_lake.lake.parquet import export_series, export_warehouse
from app.data_lake.schemas import OhlcvBar
from app.data_lake.warehouse.ohlcv import reset_memory_store, upsert_bars


def setup_function() -> None:
    reset_memory_store()


def teardown_function() -> None:
    reset_memory_store()


def _bar(symbol: str = "BTC", hours: int = 0) -> OhlcvBar:
    return OhlcvBar(
        symbol=symbol,
        timeframe="1h",
        ts=datetime(2026, 8, 27, hours, tzinfo=UTC),
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
    )


def test_export_disabled_without_path(monkeypatch) -> None:
    monkeypatch.setattr("app.config.settings.data_lake_path", "")
    monkeypatch.setattr("app.data_lake.lake.parquet.settings.data_lake_path", "")
    result = export_warehouse()
    assert result["reason"] == "disabled"
    assert result["exported"] == 0


def test_export_refuses_empty_warehouse(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.data_lake.lake.parquet.settings.data_lake_path", str(tmp_path))
    result = export_warehouse(root=tmp_path)
    assert result["reason"] == "empty"
    assert result["exported"] == 0
    assert list(tmp_path.glob("**/*.parquet")) == []


def test_export_writes_parquet_when_bars_exist(tmp_path: Path) -> None:
    upsert_bars([_bar("BTC", 0), _bar("BTC", 1), _bar("ETH", 0)])
    result = export_warehouse(root=tmp_path)
    assert result["reason"] == "ok"
    assert result["exported"] == 2
    btc = tmp_path / "BTC" / "1h.parquet"
    assert btc.is_file()
    frame = pd.read_parquet(btc)
    assert len(frame) == 2
    assert list(frame["close"]) == [1.5, 1.5]
    assert export_series("SOL", "1h", root=tmp_path) is None
