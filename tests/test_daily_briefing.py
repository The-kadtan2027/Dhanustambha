"""Tests for the daily briefing entrypoint helpers."""

from datetime import datetime

import pandas as pd

import scripts.daily_briefing as daily_briefing


def test_is_eod_data_expected_before_pull_time_same_day():
    """Same-day runs before the pull time should wait for NSE EOD publication."""
    current_time = datetime(2026, 4, 13, 13, 45)

    result = daily_briefing.is_eod_data_expected(
        "2026-04-13", current_time=current_time
    )

    assert result is False


def test_is_eod_data_expected_after_pull_time_same_day():
    """Same-day runs after the grace window should expect EOD data to be available."""
    current_time = datetime(2026, 4, 13, 17, 5)

    result = daily_briefing.is_eod_data_expected(
        "2026-04-13", current_time=current_time
    )

    assert result is True


def test_is_eod_data_expected_during_pull_grace_same_day():
    """Same-day runs during the grace window should still wait for publication."""
    current_time = datetime(2026, 4, 13, 16, 45)

    result = daily_briefing.is_eod_data_expected(
        "2026-04-13", current_time=current_time
    )

    assert result is False


def test_run_briefing_waits_cleanly_before_pull_time(monkeypatch, capsys):
    """run_briefing should exit cleanly before today's pull time if data is absent."""
    monkeypatch.setattr(daily_briefing, "init_db", lambda: None)
    monkeypatch.setattr(daily_briefing, "get_universe_symbols", lambda universe: ["RELIANCE"])
    monkeypatch.setattr(
        daily_briefing,
        "get_business_day_range",
        lambda start_date, end_date: ["2026-04-10", "2026-04-13"],
    )
    monkeypatch.setattr(
        daily_briefing,
        "get_stored_dates",
        lambda start_date=None, end_date=None: ["2026-04-10"],
    )
    monkeypatch.setattr(
        daily_briefing,
        "fetch_eod_data_for_dates",
        lambda symbols, fetch_dates: [],
    )
    monkeypatch.setattr(daily_briefing, "upsert_ohlcv", lambda rows: None)
    monkeypatch.setattr(
        daily_briefing,
        "is_eod_data_expected",
        lambda fetch_date, current_time=None: False,
    )

    daily_briefing.run_briefing(fetch_date="2026-04-13", history_days=1)
    captured = capsys.readouterr()

    assert "rerun after 16:30 IST + 30m grace" in captured.out


def test_run_briefing_prints_combined_and_setup_sections(monkeypatch, capsys):
    """run_briefing should show the mixed shortlist and setup-specific sections."""
    monkeypatch.setattr(daily_briefing, "init_db", lambda: None)
    monkeypatch.setattr(daily_briefing, "get_universe_symbols", lambda universe: ["RELIANCE"])
    monkeypatch.setattr(
        daily_briefing,
        "get_business_day_range",
        lambda start_date, end_date: ["2026-04-28"],
    )
    monkeypatch.setattr(
        daily_briefing,
        "get_stored_dates",
        lambda start_date=None, end_date=None: ["2026-04-28"],
    )
    monkeypatch.setattr(
        daily_briefing,
        "fetch_eod_data_for_dates",
        lambda symbols, fetch_dates: [],
    )
    monkeypatch.setattr(daily_briefing, "upsert_ohlcv", lambda rows: None)
    monkeypatch.setattr(
        daily_briefing,
        "get_all_symbols_ohlcv",
        lambda fetch_date: pd.DataFrame(
            [{"symbol": "RELIANCE", "date": "2026-04-28", "open": 100.0, "high": 110.0, "low": 99.0, "close": 108.0, "volume": 1000}]
        ),
    )
    monkeypatch.setattr(
        daily_briefing,
        "compute_breadth",
        lambda all_data: {
            "date": "2026-04-28",
            "pct_above_ma20": 80.0,
            "pct_above_ma50": 70.0,
            "new_highs_52w": 20,
            "new_lows_52w": 1,
            "up_volume_ratio": 0.75,
            "advancing": 300,
            "declining": 100,
        },
    )
    monkeypatch.setattr(daily_briefing, "compute_verdict", lambda metrics: "OFFENSIVE")
    monkeypatch.setattr(daily_briefing, "save_breadth", lambda metrics: None)

    mb_results = pd.DataFrame(
        [
            {
                "symbol": "RAILTEL",
                "setup_type": "MOMENTUM_BURST",
                "matched_setups": "MOMENTUM_BURST, EPISODIC_PIVOT",
                "score": 100.0,
                "pct_change": 10.0,
                "volume_ratio": 5.0,
                "close": 200.0,
            }
        ]
    )
    ep_results = pd.DataFrame(
        [
            {
                "symbol": "M&MFIN",
                "setup_type": "EPISODIC_PIVOT",
                "matched_setups": "EPISODIC_PIVOT",
                "score": 90.0,
                "pct_change": 6.0,
                "volume_ratio": 4.0,
                "close": 300.0,
            }
        ]
    )
    ti_results = pd.DataFrame(
        [
            {
                "symbol": "ONGC",
                "setup_type": "TREND_INTENSITY",
                "matched_setups": "TREND_INTENSITY, MOMENTUM_BURST",
                "score": 80.0,
                "pct_change": 3.0,
                "volume_ratio": 2.0,
                "close": 250.0,
            }
        ]
    )
    monkeypatch.setattr(daily_briefing, "detect_momentum_burst", lambda all_data: mb_results)
    monkeypatch.setattr(daily_briefing, "detect_episodic_pivot", lambda all_data: ep_results)
    monkeypatch.setattr(daily_briefing, "detect_trend_intensity", lambda all_data: ti_results)
    monkeypatch.setattr(
        daily_briefing,
        "merge_and_rank",
        lambda results, scan_date: pd.concat(results, ignore_index=True),
    )
    monkeypatch.setattr(
        daily_briefing,
        "export_watchlist",
        lambda watchlist, scan_date: f"data/watchlists/{scan_date}.csv",
    )

    daily_briefing.run_briefing(fetch_date="2026-04-28", history_days=1)
    captured = capsys.readouterr()

    assert "TOP CANDIDATES (3)" in captured.out
    assert "TOP MOMENTUM BURST (1)" in captured.out
    assert "TOP EPISODIC PIVOT (1)" in captured.out
    assert "TOP TREND INTENSITY (1)" in captured.out
