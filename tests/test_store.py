"""Tests for the SQLite storage layer."""

import os
import sqlite3
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Use a temp DB for every test and avoid touching the real market DB."""
    db_path = str(tmp_path / "test_market.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    return db_path


def test_init_db_creates_tables(tmp_db):
    """init_db should create the required SQLite tables."""
    from src.ingestion.store import init_db

    init_db()

    conn = sqlite3.connect(tmp_db)
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()

    assert "ohlcv" in tables
    assert "symbols" in tables
    assert "breadth" in tables
    assert "watchlist" in tables
    assert "trades" in tables


def test_upsert_ohlcv_inserts_new_row(tmp_db):
    """upsert_ohlcv should insert a new OHLCV row."""
    from src.ingestion.store import init_db, upsert_ohlcv

    init_db()

    rows = [
        {
            "symbol": "RELIANCE",
            "date": "2026-04-11",
            "open": 1200.0,
            "high": 1220.0,
            "low": 1195.0,
            "close": 1215.0,
            "volume": 500000,
        }
    ]

    upsert_ohlcv(rows)

    conn = sqlite3.connect(tmp_db)
    result = conn.execute(
        "SELECT close FROM ohlcv WHERE symbol='RELIANCE' AND date='2026-04-11'"
    ).fetchone()
    conn.close()

    assert result is not None
    assert result[0] == 1215.0


def test_upsert_ohlcv_updates_existing_row(tmp_db):
    """upsert_ohlcv should replace an existing row for the same symbol/date."""
    from src.ingestion.store import init_db, upsert_ohlcv

    init_db()

    rows = [
        {
            "symbol": "TCS",
            "date": "2026-04-11",
            "open": 3500.0,
            "high": 3550.0,
            "low": 3480.0,
            "close": 3520.0,
            "volume": 300000,
        }
    ]

    upsert_ohlcv(rows)
    rows[0]["close"] = 3530.0
    upsert_ohlcv(rows)

    conn = sqlite3.connect(tmp_db)
    count = conn.execute(
        "SELECT COUNT(*) FROM ohlcv WHERE symbol='TCS'"
    ).fetchone()[0]
    close = conn.execute(
        "SELECT close FROM ohlcv WHERE symbol='TCS'"
    ).fetchone()[0]
    conn.close()

    assert count == 1
    assert close == 3530.0


def test_get_ohlcv_returns_dataframe(tmp_db):
    """get_ohlcv should return the requested rows as a DataFrame."""
    from src.ingestion.store import get_ohlcv, init_db, upsert_ohlcv

    init_db()

    rows = [
        {
            "symbol": "INFY",
            "date": "2026-04-09",
            "open": 1400.0,
            "high": 1420.0,
            "low": 1395.0,
            "close": 1410.0,
            "volume": 200000,
        },
        {
            "symbol": "INFY",
            "date": "2026-04-10",
            "open": 1410.0,
            "high": 1430.0,
            "low": 1405.0,
            "close": 1425.0,
            "volume": 220000,
        },
    ]

    upsert_ohlcv(rows)
    df = get_ohlcv("INFY", days=30)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "close" in df.columns
    assert "volume" in df.columns


def test_get_stored_dates_returns_sorted_distinct_dates(tmp_db):
    """get_stored_dates should return ordered unique stored trading dates."""
    from src.ingestion.store import get_stored_dates, init_db, upsert_ohlcv

    init_db()

    rows = [
        {
            "symbol": "INFY",
            "date": "2026-04-10",
            "open": 1410.0,
            "high": 1430.0,
            "low": 1405.0,
            "close": 1425.0,
            "volume": 220000,
        },
        {
            "symbol": "TCS",
            "date": "2026-04-09",
            "open": 3500.0,
            "high": 3550.0,
            "low": 3480.0,
            "close": 3520.0,
            "volume": 300000,
        },
        {
            "symbol": "INFY",
            "date": "2026-04-09",
            "open": 1400.0,
            "high": 1420.0,
            "low": 1395.0,
            "close": 1410.0,
            "volume": 200000,
        },
    ]

    upsert_ohlcv(rows)

    assert get_stored_dates() == ["2026-04-09", "2026-04-10"]
