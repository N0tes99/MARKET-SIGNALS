"""Procedural expansion knobs and OHLCV warehouse (in-memory path)."""

from datetime import UTC, datetime, timedelta

import pandas as pd

from app.data_lake.ops import alembic_head, lake_ops_snapshot
from app.data_lake.schemas import OhlcvBar
from app.data_lake.warehouse.ohlcv import (
    get_bars,
    persist_ohlcv_frame,
    reset_memory_store,
    upsert_bars,
    warehouse_status,
)
from app.engines.expansion_engine.config import (
    DEFAULT_EXPANSION_CONFIG,
    default_expansion_config,
    expansion_config_from_dict,
)
from app.market_data.normalizer import STANDARD_COLUMNS
from app.memory.procedural.config_store import (
    load_expansion_config,
    reset_process_overlay,
    save_expansion_config,
)


def setup_function() -> None:
    reset_process_overlay()
    reset_memory_store()


def teardown_function() -> None:
    reset_process_overlay()
    reset_memory_store()


def test_file_defaults_when_nothing_saved() -> None:
    cfg = default_expansion_config()
    assert cfg.trigger_net_score == DEFAULT_EXPANSION_CONFIG.trigger_net_score
    assert cfg.universe == DEFAULT_EXPANSION_CONFIG.universe


def test_save_overlay_is_visible_to_live_config() -> None:
    mutated = expansion_config_from_dict({"trigger_net_score": 91.0})
    save_expansion_config(mutated)
    live = load_expansion_config()
    assert live.trigger_net_score == 91.0
    assert live.watch_net_score == DEFAULT_EXPANSION_CONFIG.watch_net_score


def test_unknown_knobs_are_ignored() -> None:
    cfg = expansion_config_from_dict({"not_a_knob": 1, "trigger_volume_mult": 2.5})
    assert cfg.trigger_volume_mult == 2.5


def test_warehouse_roundtrip_memory() -> None:
    ts = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    upsert_bars(
        [
            OhlcvBar(
                symbol="BTC",
                timeframe="1h",
                ts=ts,
                open=1,
                high=2,
                low=0.5,
                close=1.5,
                volume=10,
            )
        ]
    )
    bars = get_bars("BTC", "1h", limit=10)
    assert bars
    assert bars[-1].close == 1.5


def test_persist_frame_skips_one_minute() -> None:
    ts = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)
    df = pd.DataFrame(
        [
            {
                "timestamp": ts,
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "volume": 3.0,
            }
        ],
        columns=STANDARD_COLUMNS,
    )
    assert persist_ohlcv_frame(df, symbol="ETH", timeframe="1m") == 0
    assert persist_ohlcv_frame(df, symbol="ETH", timeframe="1h") == 1
    assert get_bars("ETH", "1h")[-1].close == 1.05


def test_warehouse_orders_bars_oldest_first() -> None:
    base = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
    upsert_bars(
        [
            OhlcvBar("WH1", "1h", base + timedelta(hours=2), 3, 3, 3, 3, 1),
            OhlcvBar("WH1", "1h", base, 1, 1, 1, 1, 1),
            OhlcvBar("WH1", "1h", base + timedelta(hours=1), 2, 2, 2, 2, 1),
        ]
    )
    closes = [b.close for b in get_bars("WH1", "1h")]
    assert closes == [1.0, 2.0, 3.0]


def test_warehouse_status_counts_memory_bars() -> None:
    ts = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
    upsert_bars(
        [
            OhlcvBar("AAA", "1h", ts, 1, 1, 1, 1, 1),
            OhlcvBar("BBB", "1h", ts, 2, 2, 2, 2, 1),
        ]
    )
    status = warehouse_status()
    assert status["backend"] == "memory"
    assert status["table_present"] is False
    assert status["bar_count"] == 2
    assert status["symbol_count"] == 2
    assert status["latest_ts"] == ts
    snap = lake_ops_snapshot()
    assert snap["warehouse"]["bar_count"] == 2
    assert snap["alembic"]["source"] == "skipped"
    assert alembic_head()
