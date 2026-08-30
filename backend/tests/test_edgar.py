"""EDGAR 8-K overlay for Radar catalyst."""

from datetime import date

from app.engines.runner_engine.scoring.edgar import (
    _FILING_CACHE,
    EdgarSnapshot,
    _parse_filings,
    directory_from_tickers_payload,
    fetch_edgar_snapshot,
)
from app.engines.runner_engine.scoring.yahoo_dims import score_catalyst
from app.engines.runner_engine.scoring.yahoo_snapshot import empty_yahoo_snapshot


def test_parse_filings_counts_recent_8k() -> None:
    payload = {
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q", "8-K"],
                "filingDate": ["2026-08-20", "2026-08-01", "2026-07-01"],
            }
        }
    }
    count, form, filed = _parse_filings(payload, today=date(2026, 8, 27), window=14)
    assert count == 1
    assert form == "8-K"
    assert filed == date(2026, 8, 20)


def test_parse_filings_counts_6k() -> None:
    payload = {
        "filings": {
            "recent": {
                "form": ["6-K", "20-F"],
                "filingDate": ["2026-08-26", "2026-08-01"],
            }
        }
    }
    count, form, filed = _parse_filings(payload, today=date(2026, 8, 27), window=14)
    assert count == 1
    assert form == "6-K"
    assert filed == date(2026, 8, 26)


def test_parse_filings_empty_payload() -> None:
    count, form, filed = _parse_filings({}, today=date(2026, 8, 27), window=14)
    assert count == 0
    assert form is None
    assert filed is None


def test_catalyst_missing_without_earnings_or_edgar() -> None:
    dim = score_catalyst(empty_yahoo_snapshot("CRDO"), today=date(2026, 8, 27))
    assert dim.data_quality == "missing"
    assert dim.score == 50.0


def test_fetch_empty_when_unknown_ticker(monkeypatch) -> None:
    _FILING_CACHE.clear()
    monkeypatch.setattr(
        "app.engines.runner_engine.scoring.edgar.lookup_cik",
        lambda symbol: None,
    )
    snap = fetch_edgar_snapshot("ZZZZ", today=date(2026, 8, 27))
    assert snap.cik is None
    assert snap.eight_k_count == 0


def test_directory_keeps_issuer_title() -> None:
    directory = directory_from_tickers_payload(
        {"0": {"cik_str": 1477430, "ticker": "CLS", "title": "Celestica Inc."}}
    )
    assert directory.title_by_symbol["CLS"] == "Celestica Inc."
    assert directory.cik_by_symbol["CLS"] == "0001477430"


def test_catalyst_from_edgar_without_earnings() -> None:
    edgar = EdgarSnapshot(
        symbol="CRDO",
        cik="000123",
        eight_k_count=2,
        latest_form="8-K",
        latest_date=date(2026, 8, 25),
    )
    dim = score_catalyst(
        empty_yahoo_snapshot("CRDO"),
        today=date(2026, 8, 27),
        edgar=edgar,
    )
    assert dim.data_quality == "good"
    assert dim.score > 50
    assert any("EDGAR 8-K" in line for line in dim.factors)
    assert any("Fresh 8-K" in line for line in dim.conflicts)
