"""Process-wide caps so Render's 512MB web dyno does not OOM on dashboard load.

Glibc creates a malloc arena per thread (~64MB). Sixteen warm workers plus
eight evaluate workers plus six scanner workers used to spike past the limit
the moment the home page fans out /assets, paper, Radar, and Expansion.
"""

# Parallel OHLCV prefetch inside MarketDataService.warm.
OHLCV_WARM_WORKERS = 4
# DecisionPipelineService.rank_all evaluate pool.
RANK_EVAL_WORKERS = 4
# Radar / expansion / perps / setups / futures / perp-v2 scanners.
SCAN_WORKERS = 3
# In-process OHLCV DataFrame cache (unique symbol:timeframe:limit keys).
OHLCV_CACHE_MAX_ENTRIES = 96
CHART_OHLCV_CACHE_MAX_ENTRIES = 48
EVAL_CACHE_MAX_ENTRIES = 80
