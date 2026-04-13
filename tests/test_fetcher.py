"""Tests for symbol universe lookup and EOD fetch parsing."""

import pandas as pd
import src.ingestion.fetcher as fetcher

from src.ingestion.fetcher import normalize_nselib_bhavcopy, parse_bhavcopy_rows
from src.ingestion.symbols import get_universe_symbols


def test_parse_bhavcopy_csv_extracts_ohlcv():
    """parse_bhavcopy_rows should convert EQ rows into OHLCV dicts."""
    sample_rows = [
        {
            "SYMBOL": "RELIANCE",
            "SERIES": "EQ",
            "OPEN": "1200.00",
            "HIGH": "1220.00",
            "LOW": "1195.00",
            "CLOSE": "1215.00",
            "TOTTRDQTY": "500000",
        },
        {
            "SYMBOL": "TCS",
            "SERIES": "EQ",
            "OPEN": "3500.00",
            "HIGH": "3550.00",
            "LOW": "3480.00",
            "CLOSE": "3520.00",
            "TOTTRDQTY": "300000",
        },
        {
            "SYMBOL": "RELIANCE",
            "SERIES": "BE",
            "OPEN": "1200.00",
            "HIGH": "1220.00",
            "LOW": "1195.00",
            "CLOSE": "1215.00",
            "TOTTRDQTY": "100",
        },
    ]

    result = parse_bhavcopy_rows(sample_rows, date="2026-04-11")

    assert len(result) == 2
    assert result[0]["symbol"] == "RELIANCE"
    assert result[0]["close"] == 1215.0
    assert result[0]["volume"] == 500000
    assert result[0]["date"] == "2026-04-11"


def test_parse_bhavcopy_skips_non_eq_series():
    """parse_bhavcopy_rows should ignore non-EQ instrument series."""
    sample_rows = [
        {
            "SYMBOL": "NIFTY",
            "SERIES": "INDEX",
            "OPEN": "22000",
            "HIGH": "22100",
            "LOW": "21950",
            "CLOSE": "22050",
            "TOTTRDQTY": "0",
        }
    ]

    result = parse_bhavcopy_rows(sample_rows, date="2026-04-11")

    assert len(result) == 0


def test_normalize_nselib_bhavcopy_extracts_eq_rows():
    """normalize_nselib_bhavcopy should map NSE bhavcopy columns into OHLCV rows."""
    df = pd.DataFrame(
        [
            {
                "TckrSymb": "RELIANCE",
                "SctySrs": "EQ",
                "OpnPric": 1200.0,
                "HghPric": 1220.0,
                "LwPric": 1195.0,
                "ClsPric": 1215.0,
                "TtlTradgVol": 500000,
            },
            {
                "TckrSymb": "TCS",
                "SctySrs": "EQ",
                "OpnPric": 3500.0,
                "HghPric": 3550.0,
                "LwPric": 3480.0,
                "ClsPric": 3520.0,
                "TtlTradgVol": 300000,
            },
            {
                "TckrSymb": "NIFTY",
                "SctySrs": "INDEX",
                "OpnPric": 22000.0,
                "HghPric": 22100.0,
                "LwPric": 21950.0,
                "ClsPric": 22050.0,
                "TtlTradgVol": 0,
            },
        ]
    )

    result = normalize_nselib_bhavcopy(df, fetch_date="2025-04-11")

    assert len(result) == 2
    assert result[0]["symbol"] == "RELIANCE"
    assert result[0]["close"] == 1215.0
    assert result[0]["volume"] == 500000
    assert result[0]["date"] == "2025-04-11"


def test_get_business_day_range_skips_weekends():
    """get_business_day_range should return only business dates."""
    result = fetcher.get_business_day_range("2025-04-11", "2025-04-15")

    assert result == ["2025-04-11", "2025-04-14", "2025-04-15"]


def test_fetch_eod_data_range_aggregates_rows(monkeypatch):
    """fetch_eod_data_range should combine rows across business dates and skip empties."""
    def fake_fetch(symbols, fetch_date):
        if fetch_date == "2025-04-14":
            return []
        return [
            {
                "symbol": "RELIANCE",
                "date": fetch_date,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 500000,
            }
        ]

    monkeypatch.setattr(fetcher, "fetch_eod_data", fake_fetch)

    rows = fetcher.fetch_eod_data_range(
        ["RELIANCE"], "2025-04-11", "2025-04-15", pause_seconds=0.0
    )

    assert len(rows) == 2
    assert [row["date"] for row in rows] == ["2025-04-11", "2025-04-15"]


def test_get_nifty500_symbols_returns_list():
    """get_universe_symbols should return a non-empty list for the test universe."""
    symbols = get_universe_symbols("NIFTY50_TEST")

    assert isinstance(symbols, list)
    assert len(symbols) > 0
    assert all(isinstance(symbol, str) for symbol in symbols)
