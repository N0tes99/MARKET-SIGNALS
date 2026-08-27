"""Radar Discord fires on list upgrades after a silent baseline."""

from app.engines.runner_engine.radar_alerts import note_scan, reset_radar_alert_state
from app.engines.runner_engine.types import RunnerCandidate, RunnerScores


def _cand(
    symbol: str,
    watch: str,
    signal: str = "none",
    gate: str = "none",
) -> RunnerCandidate:
    return RunnerCandidate(
        id=f"{symbol}-x",
        symbol=symbol,
        stage="ignition" if watch == "ignition" else "early_accumulation",
        signal_type=signal,  # type: ignore[arg-type]
        watchlist=watch,  # type: ignore[arg-type]
        alert_gate=gate,  # type: ignore[arg-type]
        scores=RunnerScores(runner_score=80.0),
    )


def test_baseline_scan_is_silent() -> None:
    reset_radar_alert_state()
    fired = note_scan([_cand("NBIS", "early", "accumulation")])
    assert fired == []


def test_early_to_ignition_fires_once() -> None:
    reset_radar_alert_state()
    note_scan([_cand("NBIS", "early", "accumulation")])
    fired = note_scan([_cand("NBIS", "ignition", "ignition")])
    assert fired == ["NBIS:ignition"]
    again = note_scan([_cand("NBIS", "ignition", "ignition")])
    assert again == []


def test_jump_to_running_and_failure() -> None:
    reset_radar_alert_state()
    note_scan([_cand("CRDO", "ignition", "ignition")])
    fired = note_scan([_cand("CRDO", "running", "confirmed_runner")])
    assert fired == ["CRDO:running"]
    fail = note_scan([_cand("CRDO", "running", "runner_failure")])
    assert fail == ["CRDO:runner_failure"]


def test_early_gate_fires_after_baseline() -> None:
    reset_radar_alert_state()
    note_scan([_cand("NBIS", "early", "accumulation")])
    fired = note_scan([_cand("NBIS", "early", "accumulation", gate="early")])
    assert fired == ["NBIS:early"]
    again = note_scan([_cand("NBIS", "early", "accumulation", gate="early")])
    assert again == []


def test_high_gate_fires_after_baseline() -> None:
    reset_radar_alert_state()
    note_scan([_cand("CRDO", "ignition", "ignition")])
    fired = note_scan([_cand("CRDO", "ignition", "ignition", gate="high")])
    assert fired == ["CRDO:high"]
    again = note_scan([_cand("CRDO", "ignition", "ignition", gate="high")])
    assert again == []
