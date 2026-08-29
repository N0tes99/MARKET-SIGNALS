"""13F EDGAR search into Radar replay institutional_accum — not live Yahoo."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from app.engines.runner_engine.backtest.pit import build_dated_series, load_dated_fundamentals
from app.engines.runner_engine.backtest.study import run_study
from app.engines.runner_engine.scoring.edgar import directory_from_tickers_payload
from app.engines.runner_engine.scoring.thirteen_f import (
    _SEARCH_YEARS,
    INCOMPLETE_UNIVERSE_FACTOR,
    ThirteenFHit,
    ThirteenFSearchResult,
    _search_windows,
    efts_search_params,
    parse_efts_hits,
    score_institutional_13f,
    search_queries,
)

EFTS_FIXTURE = {
    "hits": {
        "total": {"value": 3, "relation": "eq"},
        "hits": [
            {
                "_id": "0000902664-20-004111:infotable.xml",
                "_source": {
                    "adsh": "0000902664-20-004111",
                    "ciks": ["0000902664"],
                    "file_date": "2020-11-16",
                    "period_ending": "2020-09-30",
                    "form": "13F-HR",
                },
            },
            {
                "_id": "0001067983-21-000028:primary_doc.xml",
                "_source": {
                    "ciks": ["0001067983"],
                    "file_date": "2021-02-16",
                    "period_ending": "2020-12-31",
                    "form": "13F-HR",
                },
            },
            {
                "_id": "0001067983-21-000028:holdings.xml",
                "_source": {
                    "ciks": ["0001067983"],
                    "file_date": "2021-02-16",
                    "form": "13F-HR",
                },
            },
            {
                "_id": "0000315066-22-000040:primary_doc.xml",
                "_source": {
                    "ciks": ["0000315066"],
                    "file_date": "2022-02-14",
                    "period_ending": "2021-12-31",
                    "form": "13F-HR",
                },
            },
        ],
    }
}


def test_parse_efts_hits_dedupes_accession() -> None:
    hits = parse_efts_hits(EFTS_FIXTURE)
    accessions = [h.accession for h in hits]
    assert accessions == [
        "0000902664-20-004111",
        "0001067983-21-000028",
        "0000315066-22-000040",
    ]
    assert hits[0].file_date == date(2020, 11, 16)
    assert hits[0].filer_cik == "0000902664"


def test_file_date_after_as_of_does_not_count() -> None:
    result = ThirteenFSearchResult(hits=tuple(parse_efts_hits(EFTS_FIXTURE)))
    early = score_institutional_13f(result, date(2020, 6, 1))
    assert early.data_quality == "missing"
    assert early.score == 50.0
    later = score_institutional_13f(result, date(2020, 11, 16))
    assert later.data_quality == "degraded"
    assert any("1 unique 13F filers" in line for line in later.factors)


def test_period_ending_is_not_the_knowable_date() -> None:
    result = ThirteenFSearchResult(hits=tuple(parse_efts_hits(EFTS_FIXTURE)))
    # period_ending is 2020-09-30; file_date is 2020-11-16
    as_of_period = score_institutional_13f(result, date(2020, 10, 1))
    assert as_of_period.data_quality == "missing"


def test_rising_coverage_scores_above_neutral() -> None:
    hits = (
        ThirteenFHit("a-2019", date(2019, 11, 14), "0000000001"),
        ThirteenFHit("b-2020", date(2020, 11, 16), "0000000001"),
        ThirteenFHit("c-2020", date(2020, 11, 16), "0000000002"),
        ThirteenFHit("d-2020", date(2020, 12, 1), "0000000003"),
    )
    dim = score_institutional_13f(ThirteenFSearchResult(hits=hits), date(2020, 12, 1))
    assert dim.data_quality == "degraded"
    assert dim.score > 50.0
    assert INCOMPLETE_UNIVERSE_FACTOR in dim.factors
    assert any("Rising 13F filer coverage" in line for line in dim.factors)
    blob = " ".join(dim.factors)
    assert "Institutions 72%" not in blob
    assert "Ownership snapshot" not in blob


def test_shrinking_coverage_is_a_conflict() -> None:
    hits = (
        ThirteenFHit("a-2019", date(2019, 2, 14), "0000000001"),
        ThirteenFHit("b-2019", date(2019, 2, 14), "0000000002"),
        ThirteenFHit("c-2020", date(2020, 2, 14), "0000000001"),
    )
    dim = score_institutional_13f(ThirteenFSearchResult(hits=hits), date(2020, 2, 14))
    assert dim.score < 50.0
    assert any("Shrinking" in line for line in dim.conflicts)


def test_short_ticker_not_used_as_sole_query() -> None:
    queries = search_queries("CLS", "Celestica Inc.")
    assert queries == ('"Celestica Inc."',)
    assert "CLS" not in queries
    long_ticker = search_queries("CRDO", "Credo Technology Group Holding Ltd")
    assert '"Credo Technology Group Holding Ltd"' in long_ticker
    assert "CRDO" in long_ticker
    short_no_title = search_queries("KO", None)
    assert short_no_title == ()


def test_issuer_title_from_company_tickers_payload() -> None:
    directory = directory_from_tickers_payload(
        {
            "0": {"cik_str": 1477430, "ticker": "CLS", "title": "Celestica Inc."},
            "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        }
    )
    assert directory.title_by_symbol["CLS"] == "Celestica Inc."
    assert directory.cik_by_symbol["CLS"] == "0001477430"


def test_build_dated_series_emits_institutional_accum() -> None:
    hits = ThirteenFSearchResult(
        hits=(
            ThirteenFHit("a-2020", date(2020, 3, 1), "0000000001"),
            ThirteenFHit("b-2020", date(2020, 3, 1), "0000000002"),
        )
    )
    dated = build_dated_series(
        "WIN",
        revenue_series=((date(2019, 12, 31), 90.0),),
        filings=((date(2020, 3, 1), "8-K"),),
        thirteen_f=hits,
    )
    assert dated
    inst_dates = {snap.as_of for snap in dated}
    assert date(2020, 3, 1) in inst_dates
    for snap in dated:
        inst = snap.dimensions["institutional_accum"]
        assert INCOMPLETE_UNIVERSE_FACTOR in inst.factors
        blob = " ".join(inst.factors)
        assert "Institutions 72%" not in blob
        assert "Yahoo" not in blob
    filled = [s for s in dated if s.as_of == date(2020, 3, 1)][0]
    assert filled.dimensions["institutional_accum"].data_quality == "degraded"
    assert filled.dimensions["catalyst"].name == "catalyst"
    assert filled.dimensions["fundamental"].name == "fundamental"


def test_load_dated_fundamentals_uses_injected_13f() -> None:
    hits = ThirteenFSearchResult(
        hits=(ThirteenFHit("a-2020", date(2020, 5, 15), "0000000001"),)
    )
    out = load_dated_fundamentals(
        ("WIN",),
        filings_fetcher=lambda _s: (),
        revenue_fetcher=lambda _s: ((date(2019, 12, 31), 80.0),),
        thirteen_f_fetcher=lambda _s: hits,
    )
    series = out["WIN"]
    inst = next(s.dimensions["institutional_accum"] for s in series if s.as_of == date(2020, 5, 15))
    assert inst.data_quality == "degraded"
    assert INCOMPLETE_UNIVERSE_FACTOR in inst.factors


@pytest.mark.asyncio
async def test_backtest_api_look_ahead_mentions_13f(client: AsyncClient, monkeypatch) -> None:
    from datetime import UTC, datetime, timedelta

    import pandas as pd

    from app.market_data.normalizer import STANDARD_COLUMNS

    origin = datetime(2019, 10, 1, tzinfo=UTC)
    rows = []
    close = 10.0
    for i in range(250):
        close *= 1.01
        rows.append(
            {
                "timestamp": origin + timedelta(days=i),
                "open": close,
                "high": close * 1.01,
                "low": close * 0.99,
                "close": close,
                "volume": 1_000.0 + i,
            }
        )
    df = pd.DataFrame(rows, columns=STANDARD_COLUMNS)
    dated = {
        "WIN": build_dated_series(
            "WIN",
            revenue_series=(
                (date(2019, 6, 30), 50.0),
                (date(2019, 9, 30), 60.0),
                (date(2019, 12, 31), 90.0),
            ),
            filings=((date(2020, 3, 1), "8-K"),),
            thirteen_f=ThirteenFSearchResult(
                hits=(ThirteenFHit("a-2020", date(2020, 3, 1), "0000000001"),)
            ),
        )
    }

    def _fake_cached(**kwargs):
        return run_study(
            {"WIN": df, "SMH": df},
            symbols=("WIN",),
            dated_fundamentals=dated,
            mode="dated_fundamentals",
        )

    monkeypatch.setattr("app.api.routes.runners.cached_live_study", _fake_cached)
    resp = await client.get("/api/v1/runners/backtest")
    assert resp.status_code == 200
    body = resp.json()
    look = body["look_ahead"].lower()
    assert "13f" in look
    assert "not a complete manager universe" in look
    assert "filing" in look
    assert body["phase"] == "6_13f"
    assert body["mode"] == "dated_fundamentals"


def test_efts_params_use_single_13f_hr_form() -> None:
    params = efts_search_params('"Celestica Inc."', date(2024, 1, 1), date(2024, 12, 31))
    forms = [value for key, value in params if key == "forms"]
    assert forms == ["13F-HR"]
    assert [key for key, _value in params].count("forms") == 1


def test_search_windows_cover_two_year_lookback() -> None:
    windows = _search_windows(as_of=date(2026, 8, 29))
    starts = [start for start, _end in windows]
    assert min(starts) <= date(2019, 1, 1)
    assert len(windows) == _SEARCH_YEARS


def test_prior_outside_coverage_is_not_rising() -> None:
    hits = (ThirteenFHit("a-2022", date(2022, 2, 14), "0000000001"),)
    dim = score_institutional_13f(
        ThirteenFSearchResult(hits=hits, coverage_start=date(2022, 1, 1)),
        date(2022, 6, 1),
    )
    assert dim.data_quality == "missing"
    assert dim.score == 50.0
    assert any("not in search coverage" in line for line in dim.factors)
    assert not any("Rising" in line for line in dim.factors)


def test_incomplete_fetch_is_not_scored() -> None:
    hits = (
        ThirteenFHit("a-2020", date(2020, 2, 14), "0000000001"),
        ThirteenFHit("b-2019", date(2019, 2, 14), "0000000002"),
        ThirteenFHit("c-2019", date(2019, 2, 14), "0000000003"),
    )
    dim = score_institutional_13f(
        ThirteenFSearchResult(hits=hits, incomplete=True),
        date(2020, 2, 14),
    )
    assert dim.data_quality == "missing"
    assert dim.score == 50.0
    assert any("partial 13F search" in line for line in dim.factors)
    assert dim.conflicts == []


def test_capped_keeps_incomplete_factor() -> None:
    hits = (ThirteenFHit("a-2020", date(2020, 11, 16), "0000000001"),)
    dim = score_institutional_13f(
        ThirteenFSearchResult(hits=hits, capped=True),
        date(2020, 11, 16),
    )
    assert dim.data_quality == "degraded"
    assert any("search result cap reached" in line for line in dim.factors)


def test_13f_only_event_keeps_earlier_fundamentals() -> None:
    dated = build_dated_series(
        "WIN",
        revenue_series=(
            (date(2019, 3, 31), 50.0),
            (date(2019, 6, 30), 60.0),
            (date(2019, 9, 30), 80.0),
            (date(2019, 12, 31), 110.0),
        ),
        filings=(),
        thirteen_f=ThirteenFSearchResult(
            hits=(ThirteenFHit("a-2020", date(2020, 6, 1), "0000000001"),)
        ),
    )
    inst_snap = next(snap for snap in dated if snap.as_of == date(2020, 6, 1))
    assert inst_snap.dimensions["fundamental"].data_quality != "missing"
    assert inst_snap.dimensions["institutional_accum"].data_quality == "degraded"


def test_live_yahoo_institutional_still_labels_snapshot() -> None:
    from app.engines.runner_engine.scoring.yahoo_dims import score_institutional
    from app.engines.runner_engine.scoring.yahoo_snapshot import YahooRunnerSnapshot

    dim = score_institutional(
        YahooRunnerSnapshot(
            symbol="WIN",
            fetched_ok=True,
            held_percent_institutions=0.72,
        )
    )
    assert any("Ownership snapshot (not 13F change)" in line for line in dim.factors)
    assert any("Institutions" in line for line in dim.factors)


def test_efts_headers_use_sec_user_agent() -> None:
    from app.config import settings
    from app.engines.runner_engine.scoring.thirteen_f import _headers

    assert _headers()["User-Agent"] == settings.sec_user_agent
