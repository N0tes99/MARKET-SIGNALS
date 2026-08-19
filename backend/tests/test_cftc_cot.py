"""CFTC COT overlay — index, strengthen/weaken, skip crowded tape."""

from __future__ import annotations

from datetime import date, timedelta

from app.market_data.providers.cftc_cot import (
    COT_BY_YAHOO,
    SCORE_TILT,
    CotSnapshot,
    _snapshot_from_rows,
    clear_cot_cache,
    cot_fights_direction,
    cot_index,
    fetch_cot_snapshot,
    overlay_for_direction,
)


def _snap(*, idx: float, spec_net: float = 1.0) -> CotSnapshot:
    return CotSnapshot(
        symbol="ES=F",
        market_code="13874A",
        book="tff",
        report_date=date(2026, 8, 11),
        spec_long=200_000,
        spec_short=100_000,
        spec_net=spec_net,
        open_interest=2_119_506,
        cot_index=idx,
        contract_name="E-MINI S&P 500",
    )


def test_cot_index_needs_eight_weeks() -> None:
    assert cot_index([1.0, 2.0, 3.0]) is None
    assert cot_index([5.0] * 8) == 50.0
    assert cot_index(list(range(10))) == 100.0
    assert cot_index(list(reversed(range(10)))) == 0.0


def test_overlay_strengthen_and_weaken() -> None:
    crowded_long = _snap(idx=92.0, spec_net=400_000)
    weak = overlay_for_direction("long", crowded_long)
    assert weak.effect == "weaken"
    assert weak.skip_paper is True
    assert weak.delta == -SCORE_TILT
    assert weak.conflict is not None

    fuel = overlay_for_direction("short", crowded_long)
    assert fuel.effect == "strengthen"
    assert fuel.skip_paper is False
    assert fuel.delta == SCORE_TILT

    crowded_short = _snap(idx=12.0, spec_net=-280_000)
    assert overlay_for_direction("long", crowded_short).effect == "strengthen"
    assert overlay_for_direction("short", crowded_short).skip_paper is True
    mid = overlay_for_direction("long", _snap(idx=55.0))
    assert mid.effect == "neutral"
    assert mid.skip_paper is False
    assert mid.delta == 0.0


def test_cot_fights_direction() -> None:
    assert cot_fights_direction("long", 90.0) is True
    assert cot_fights_direction("long", 10.0) is False
    assert cot_fights_direction("short", 10.0) is True
    assert cot_fights_direction("short", 90.0) is False
    assert cot_fights_direction("long", None) is False


def test_snapshot_from_tff_history() -> None:
    spec = COT_BY_YAHOO["ES=F"]
    start = date(2026, 3, 3)
    chrono: list[dict[str, object]] = []
    for i in range(12):
        day = start + timedelta(weeks=i)
        chrono.append(
            {
                "report_date_as_yyyy_mm_dd": f"{day.isoformat()}T00:00:00.000",
                "cftc_contract_market_code": "13874A",
                "contract_market_name": "E-MINI S&P 500",
                "open_interest_all": "2119506",
                "lev_money_positions_long": str(100_000 + i * 30_000),
                "lev_money_positions_short": "400000",
            }
        )
    snap = _snapshot_from_rows(spec, list(reversed(chrono)))
    assert snap is not None
    assert snap.report_date == start + timedelta(weeks=11)
    assert snap.spec_net == 30_000
    assert snap.cot_index == 100.0
    assert snap.open_interest == 2_119_506


def test_fetch_skips_cme_crypto(monkeypatch) -> None:
    def _boom(**_kwargs):
        raise AssertionError("no CFTC for CME crypto")

    monkeypatch.setattr("app.market_data.providers.cftc_cot.shared_client", _boom)
    clear_cot_cache()
    assert fetch_cot_snapshot("BTC=F") is None
    assert fetch_cot_snapshot("ETH=F") is None
    assert fetch_cot_snapshot("MBT=F") is None


def test_fetch_fail_open(monkeypatch) -> None:
    class _Client:
        def get(self, *args, **kwargs):
            raise RuntimeError("cftc down")

    monkeypatch.setattr(
        "app.market_data.providers.cftc_cot.shared_client",
        lambda **_kwargs: _Client(),
    )
    clear_cot_cache()
    assert fetch_cot_snapshot("ES=F") is None


def test_fetch_parses_tff(monkeypatch) -> None:
    spec = COT_BY_YAHOO["ES=F"]
    start = date(2026, 3, 3)
    rows: list[dict[str, object]] = []
    for i in range(10):
        day = start + timedelta(weeks=i)
        rows.append(
            {
                "report_date_as_yyyy_mm_dd": day.isoformat(),
                "cftc_contract_market_code": spec.market_code,
                "contract_market_name": "E-MINI S&P 500",
                "open_interest_all": "2000000",
                "lev_money_positions_long": "150000",
                "lev_money_positions_short": "400000",
            }
        )
    rows = list(reversed(rows))

    class _Resp:
        status_code = 200

        def json(self):
            return rows

    class _Client:
        def get(self, url, params=None):
            assert "gpe5-46if" in url
            assert "lev_money_positions_long" in params["$select"]
            return _Resp()

    monkeypatch.setattr(
        "app.market_data.providers.cftc_cot.shared_client",
        lambda **_kwargs: _Client(),
    )
    clear_cot_cache()
    snap = fetch_cot_snapshot("ES=F")
    assert snap is not None
    assert snap.book == "tff"
    assert snap.spec_net == -250_000
    assert snap.cot_index == 50.0
