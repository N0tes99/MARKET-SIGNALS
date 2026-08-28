# Research Notes

Place research findings, data source evaluations, and strategy notes here.

## Active plans

| Plan | Status | Doc |
|------|--------|-----|
| Surface 4 — 10X Runner Detection Layer | Phase 2 preview | [10x-runner-detection-layer.md](./10x-runner-detection-layer.md) |
| Surface 6 — Rail (HL-native discovery + clerk) | Phase B scanners, paper fill | [rail-execution-surface.md](./rail-execution-surface.md) |
| Dashboard smoothness | Applied (PR) | [dashboard-smoothness.md](./dashboard-smoothness.md) |
| Futures positioning / COT overlay | Phase 1 overlay | [futures-social-positioning.md](./futures-social-positioning.md) |
| Logo boot / hologram | Implemented (hero boot + header soft) | [logo-holo-boot.md](./logo-holo-boot.md) |

## Parked (not scheduled)

| Idea | Status | Doc |
|------|--------|-----|
| Robinhood Agentic dual-MCP | Open — do not build | [robinhood-agentic-mcp.md](./robinhood-agentic-mcp.md) |

## Data Sources (To Evaluate)

- Exchange APIs (Binance, Coinbase, etc.)
- Macro data providers (FRED, Trading Economics)
- Derivatives data (Coinglass liquidations) — optional paid; leave blank; free funding/OI via Bybit→OKX remain
- **Runner Detection:** fundamentals / estimate revisions, short interest, institutional ownership, catalyst news — vendor choice open (see runner plan §10)

## Scoring Methodology

Evidence-based weighted scoring with configurable weights per category.
See `docs/architecture/overview.md` for default weight allocation.
Surface 4 uses a separate Runner Score + Risk Score (not the 13-category grade).
