"""Focused crypto perp universe — expansion radar, paper v2, perps board."""

from typing import Final

# Same slice as paper v2 / radar futures — keeps scans under ~90s cadence.
PERP_V2_UNIVERSE: Final[tuple[str, ...]] = (
    "BTC",
    "ETH",
    "SOL",
    "XRP",
    "AVAX",
    "LINK",
    "DOGE",
    "NEAR",
    "ARB",
    "APT",
    "INJ",
    "OP",
    "SUI",
    "ADA",
    "LTC",
    "DOT",
)

# Labeled replay events (Aug 2026 pump miss benchmark).
BENCHMARK_UNIVERSE: Final[tuple[str, ...]] = ("BTC", "SOL", "SUI")
