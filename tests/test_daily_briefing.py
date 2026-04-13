"""Tests for the daily briefing entrypoint helpers."""

from datetime import datetime

import scripts.daily_briefing as daily_briefing


def test_is_eod_data_expected_before_pull_time_same_day():
    """Same-day runs before the pull time should wait for NSE EOD publication."""
    current_time = datetime(2026, 4, 13, 13, 45)

    result = daily_briefing.is_eod_data_expected(
        "2026-04-13", current_time=current_time
    )

    assert result is False


def test_is_eod_data_expected_after_pull_time_same_day():
    """Same-day runs after the pull time should expect EOD data to be available."""
    current_time = datetime(2026, 4, 13, 16, 45)

    result = daily_briefing.is_eod_data_expected(
        "2026-04-13", current_time=current_time
    )

    assert result is True


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

    assert "rerun after 16:30 IST" in captured.out
