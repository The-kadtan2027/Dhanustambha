"""Tests for symbol universe lookup and EOD fetch parsing."""

import pandas as pd
import src.ingestion.fetcher as fetcher

from src.ingestion.fetcher import (
    normalize_nselib_bhavcopy,
    normalize_nselib_history,
    parse_bhavcopy_rows,
)
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


def test_normalize_nselib_history_extracts_eq_rows():
    """normalize_nselib_history should map nselib history rows into OHLCV records."""
    df = pd.DataFrame(
        [
            {
                "Symbol": "RELIANCE",
                "Series": "EQ",
                "Date": "09-Apr-2025",
                "OpenPrice": "1,169.50",
                "HighPrice": "1,189.80",
                "LowPrice": "1,168.00",
                "ClosePrice": "1,185.90",
                "TotalTradedQuantity": "85,76,832",
            },
            {
                "Symbol": "RELIANCE",
                "Series": "BE",
                "Date": "10-Apr-2025",
                "OpenPrice": "1,180.00",
                "HighPrice": "1,182.00",
                "LowPrice": "1,170.00",
                "ClosePrice": "1,171.00",
                "TotalTradedQuantity": "1,000",
            },
        ]
    )

    result = normalize_nselib_history(df, symbol="RELIANCE")

    assert len(result) == 1
    assert result[0]["symbol"] == "RELIANCE"
    assert result[0]["date"] == "2025-04-09"
    assert result[0]["open"] == 1169.5
    assert result[0]["close"] == 1185.9
    assert result[0]["volume"] == 8576832


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


# ---------------------------------------------------------------------------
# Stream A: new universe-loading tests
# ---------------------------------------------------------------------------

def test_load_index_symbols_returns_clean_strings(tmp_path, monkeypatch):
    """load_index_symbols should return deduplicated str symbols with no whitespace."""
    import io
    import pandas as pd
    import src.ingestion.symbols as sym_mod
    import config

    # Redirect cache dir to tmp so we don't touch real files
    monkeypatch.setattr(config, "UNIVERSE_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "UNIVERSE_REFRESH_DAYS", 7)

    # Fake CSV response from NSE
    fake_csv = "Company Name,Industry,Symbol,Series,ISIN Code\n" \
               "Reliance Industries,REFINERIES,RELIANCE,EQ,INE002A01018\n" \
               "Tata Consultancy Services,COMPUTERS,TCS,EQ,INE467B01029\n" \
               "Infosys Ltd.,COMPUTERS, INFY ,EQ,INE009A01021\n"

    class FakeResp:
        text = fake_csv
        def raise_for_status(self): pass

    monkeypatch.setattr("requests.get", lambda *a, **kw: FakeResp())

    symbols = sym_mod.load_index_symbols("NIFTY500")

    assert isinstance(symbols, list)
    assert len(symbols) == 3
    # No leading/trailing whitespace on any symbol
    assert all(s == s.strip() for s in symbols)
    # Known symbol present
    assert "INFY" in symbols


def test_get_universe_nifty750_deduplicates(monkeypatch):
    """NIFTY750 universe must be a deduplicated union of NIFTY500 and MICROCAP250."""
    import src.ingestion.symbols as sym_mod

    nifty500_syms = ["AAA", "BBB", "CCC"]
    microcap_syms = ["CCC", "DDD", "EEE"]  # CCC is in both

    # Stub load_index_symbols
    def fake_load(index_name):
        if index_name == "NIFTY500":
            return nifty500_syms
        if index_name == "MICROCAP250":
            return microcap_syms
        return []

    monkeypatch.setattr(sym_mod, "load_index_symbols", fake_load)

    result = sym_mod.get_universe_symbols("NIFTY750")

    assert sorted(result) == ["AAA", "BBB", "CCC", "DDD", "EEE"]
    assert len(result) == len(set(result))  # no duplicates


def test_fetch_via_yfinance_batch_extracts_row():
    """fetch_via_yfinance_batch should extract the correct date row from a batch result."""
    import pandas as pd
    from datetime import date as date_
    from src.ingestion.fetcher import fetch_via_yfinance_batch
    from unittest.mock import patch

    target_date = "2025-04-14"
    target = date_(2025, 4, 14)

    # Build a synthetic MultiIndex DataFrame that yf.download would return
    tickers = ["RELIANCE.NS", "TCS.NS"]
    fields = ["Open", "High", "Low", "Close", "Volume", "Adj Close"]
    arrays = [fields * len(tickers), [t for t in tickers for _ in fields]]
    col_index = pd.MultiIndex.from_arrays(
        [fields * len(tickers), [t for f in fields for t in tickers]],
        names=[None, None],
    )
    # Simpler: build via dict
    data = {}
    for ticker in tickers:
        data[("Open",   ticker)] = [100.0]
        data[("High",   ticker)] = [110.0]
        data[("Low",    ticker)] = [95.0]
        data[("Close",  ticker)] = [105.0]
        data[("Volume", ticker)] = [500000]
        data[("Adj Close", ticker)] = [105.0]
    raw = pd.DataFrame(data, index=pd.DatetimeIndex([target]))
    raw.columns = pd.MultiIndex.from_tuples(raw.columns)

    with patch("yfinance.download", return_value=raw):
        results = fetch_via_yfinance_batch(["RELIANCE", "TCS"], target_date)

    assert len(results) == 2
    symbols_found = {r["symbol"] for r in results}
    assert "RELIANCE" in symbols_found
    assert "TCS" in symbols_found
    assert results[0]["close"] == 105.0
    assert results[0]["date"] == target_date
