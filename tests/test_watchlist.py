"""Tests for watchlist merge and export helpers."""

from pathlib import Path

import pandas as pd

import config
from src.scanner import watchlist


def test_merge_and_rank_preserves_multi_setup_matches(monkeypatch):
    """Symbols matched by multiple scanners should retain all setup labels."""
    monkeypatch.setattr(config, "MAX_WATCHLIST_SIZE", 10)

    mb_results = pd.DataFrame(
        [
            {
                "symbol": "RAILTEL",
                "setup_type": "MOMENTUM_BURST",
                "score": 987.77,
                "pct_change": 19.23,
                "volume_ratio": 51.35,
                "close": 336.73,
                "notes": "MB hit",
            }
        ]
    )
    ep_results = pd.DataFrame(
        [
            {
                "symbol": "RAILTEL",
                "setup_type": "EPISODIC_PIVOT",
                "score": 282.61,
                "pct_change": 5.50,
                "volume_ratio": 51.35,
                "close": 336.73,
                "notes": "EP hit",
            }
        ]
    )
    ti_results = pd.DataFrame(
        [
            {
                "symbol": "KIRLOSENG",
                "setup_type": "TREND_INTENSITY",
                "score": 25.00,
                "pct_change": 5.70,
                "volume_ratio": 4.40,
                "close": 1597.00,
                "notes": "TI hit",
            }
        ]
    )

    result = watchlist.merge_and_rank(
        [mb_results, ep_results, ti_results],
        scan_date="2026-04-15",
    )

    railtel = result.loc[result["symbol"] == "RAILTEL"].iloc[0]
    assert len(result) == 2
    assert railtel["setup_type"] == "MOMENTUM_BURST"
    assert (
        railtel["matched_setups"] == "MOMENTUM_BURST, EPISODIC_PIVOT"
    )
    assert railtel["setup_match_count"] == 2


def test_export_watchlist_saves_csv_and_filters_db_columns(monkeypatch, tmp_path):
    """CSV export should keep matched metadata while DB saves only supported columns."""
    monkeypatch.setattr(config, "WATCHLIST_DIR", str(tmp_path))

    saved_records = {}

    def fake_save_watchlist(records):
        saved_records["records"] = records

    monkeypatch.setattr(watchlist, "save_watchlist", fake_save_watchlist)

    df = pd.DataFrame(
        [
            {
                "date": "2026-04-15",
                "symbol": "RAILTEL",
                "setup_type": "MOMENTUM_BURST",
                "matched_setups": "MOMENTUM_BURST, EPISODIC_PIVOT",
                "setup_match_count": 2,
                "score": 987.77,
                "pct_change": 19.23,
                "volume_ratio": 51.35,
                "close": 336.73,
                "notes": "MB hit",
            }
        ]
    )

    csv_path = watchlist.export_watchlist(df, scan_date="2026-04-15")

    exported_df = pd.read_csv(Path(csv_path))
    assert "matched_setups" in exported_df.columns
    assert "setup_match_count" in exported_df.columns
    assert csv_path == str(Path(tmp_path) / "2026-04-15.csv")

    assert "records" in saved_records
    assert saved_records["records"] == [
        {
            "date": "2026-04-15",
            "symbol": "RAILTEL",
            "setup_type": "MOMENTUM_BURST",
            "score": 987.77,
            "pct_change": 19.23,
            "volume_ratio": 51.35,
            "close": 336.73,
            "notes": "MB hit",
        }
    ]


def test_export_empty_watchlist_clears_existing_rows(monkeypatch, tmp_path):
    """A same-date empty export should remove stale DB candidates."""
    from src.ingestion.store import get_watchlist, init_db

    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "watchlist.db"))
    monkeypatch.setattr(config, "WATCHLIST_DIR", str(tmp_path))
    init_db()

    non_empty = pd.DataFrame(
        [
            {
                "date": "2026-05-21",
                "symbol": "RAILTEL",
                "setup_type": "MOMENTUM_BURST",
                "score": 10.0,
                "pct_change": 6.0,
                "volume_ratio": 2.0,
                "close": 100.0,
                "notes": "initial",
            }
        ]
    )
    watchlist.export_watchlist(non_empty, scan_date="2026-05-21")
    assert len(get_watchlist("2026-05-21")) == 1

    watchlist.export_watchlist(pd.DataFrame(), scan_date="2026-05-21")

    assert get_watchlist("2026-05-21").empty
