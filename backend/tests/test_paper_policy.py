"""Paper policy snapshot + ranking helpers."""

from __future__ import annotations

from app.engines.paper_agent.maturity import map_honest_close_outcome
from app.engines.paper_agent.paper_policy import (
    MIN_WIN_RETURN_PCT,
    attach_close_to_policy,
    candidate_rank_tier,
    momentum_fights_crowded_funding,
    parse_policy_blob,
    snapshot_paper_execution,
    sort_paper_candidates,
)
from app.engines.paper_agent.types import PaperTrade
from app.engines.runner_engine.crypto_learn import encode_paper_open_notes, parse_paper_notes


def test_l2_setups_rank_above_momentum() -> None:
    ranked = sort_paper_candidates(
        [
            {"setup_type": "perp_momentum", "score": 90.0, "symbol": "BTC"},
            {"setup_type": "funding_extreme", "score": 58.0, "symbol": "ETH"},
            {"setup_type": "liq_flush", "score": 60.0, "symbol": "SOL"},
        ]
    )
    assert [c["setup_type"] for c in ranked] == [
        "liq_flush",
        "funding_extreme",
        "perp_momentum",
    ]
    assert candidate_rank_tier("funding_extreme") == 1
    assert candidate_rank_tier("perp_momentum") == 0


def test_momentum_fights_crowded_funding_is_directional() -> None:
    assert momentum_fights_crowded_funding("long", 10.0, 8.0) is True
    assert momentum_fights_crowded_funding("long", -10.0, 8.0) is False
    assert momentum_fights_crowded_funding("short", -10.0, 8.0) is True
    assert momentum_fights_crowded_funding("short", 10.0, 8.0) is False
    assert momentum_fights_crowded_funding("long", None, 8.0) is False


def test_policy_snapshot_roundtrip_in_notes() -> None:
    policy = snapshot_paper_execution(
        size_usd=2500.0,
        starting_cash=15_000.0,
        take_profit_pct=6.0,
        stop_loss_pct=3.0,
        source="crypto_setup",
        setup_type="funding_extreme",
        direction="short",
        confidence=68.0,
        opportunity_score=68.0,
        factors=["Funding +9 bps"],
        extras={"funding_bps": 9.0},
    )
    assert policy["schema"] == "paper_policy.v1"
    assert policy["policy_id"]
    assert policy["knobs"]["max_new_opens_per_day"] == 5
    assert policy["knobs"]["learn_min_closed_to_apply"] == 30
    assert policy["knobs"]["skip_momentum_vs_crowded_funding"] is True
    assert policy["knobs"]["skip_cme_vs_crowded_cot"] is True
    assert policy["knobs"]["max_cme_futures_opens_per_day"] == 3
    assert policy["features"]["funding_bps"] == 9.0
    same = snapshot_paper_execution(
        size_usd=2500.0,
        starting_cash=15_000.0,
        take_profit_pct=4.2,
        stop_loss_pct=2.1,
        source="crypto_perp_v2",
        setup_type="perp_momentum",
        direction="long",
        confidence=80.0,
        opportunity_score=80.0,
        extras={"funding_bps": 1.0},
    )
    assert same["policy_id"] == policy["policy_id"]

    notes = encode_paper_open_notes(
        setup_type="funding_extreme",
        direction="short",
        factors=["Funding +9 bps"],
        extras={"funding_bps": 9.0, "policy_id": policy["policy_id"], "policy": policy},
    )
    parsed = parse_paper_notes(notes)
    assert parsed["policy_id"] == policy["policy_id"]
    blob = parse_policy_blob(notes)
    assert blob is not None
    assert blob["knobs"]["size_usd"] == 2500.0
    closed_notes = f"{notes} | close=take_profit_+6.0%"
    assert parse_policy_blob(closed_notes)["policy_id"] == policy["policy_id"]


def test_tiny_return_is_not_a_win() -> None:
    from datetime import UTC, datetime

    opened = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
    noise = PaperTrade(
        id="noise",
        symbol="BTC",
        source="crypto_perp_v2",
        setup_type="perp_momentum",
        direction="long",
        fingerprint="fp",
        signal_at=opened,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="closed",
        optimistic_entry=100.0,
        optimistic_entry_at=opened,
        honest_entry=100.0,
        honest_return_pct=0.04,
        close_reason="max_hold_72h",
    )
    outcome, ret = map_honest_close_outcome(noise)
    assert ret == 0.04
    assert outcome == "breakeven"
    assert MIN_WIN_RETURN_PCT == 0.5

    stopped_trade = PaperTrade(
        id="sl",
        symbol="ETH",
        source="crypto_setup",
        setup_type="liq_flush",
        direction="long",
        fingerprint="fp2",
        signal_at=opened,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="closed",
        optimistic_entry=100.0,
        optimistic_entry_at=opened,
        honest_entry=100.0,
        honest_return_pct=-0.2,
        close_reason="stop_loss_-3.0%",
    )
    assert map_honest_close_outcome(stopped_trade)[0] == "loss"
    tp = PaperTrade(
        id="tp",
        symbol="SOL",
        source="crypto_setup",
        setup_type="funding_extreme",
        direction="short",
        fingerprint="fp3",
        signal_at=opened,
        confidence=70.0,
        opportunity_score=70.0,
        size_usd=2500.0,
        status="closed",
        optimistic_entry=100.0,
        optimistic_entry_at=opened,
        honest_entry=100.0,
        honest_return_pct=6.0,
        close_reason="take_profit_+6.0%",
    )
    assert map_honest_close_outcome(tp)[0] == "win"
    closed = attach_close_to_policy(
        {"policy_id": "abc", "knobs": {}},
        close_reason="take_profit_+6.0%",
        honest_return_pct=6.0,
        optimistic_return_pct=6.1,
        outcome="win",
    )
    assert closed["policy_id"] == "abc"
    assert closed["close"]["outcome"] == "win"
