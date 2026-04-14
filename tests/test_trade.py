"""Tests for trade sizing, logging, and summary behavior."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point the trade tests at a temporary database."""
    db_path = str(tmp_path / "trade_test.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    return db_path


def test_position_sizer_normal_case():
    """Sizing should follow fixed-fractional risk in normal conditions."""
    from src.trade.sizer import calculate_position_size

    result = calculate_position_size(
        account_size=500_000,
        entry_price=100.0,
        stop_price=95.0,
        market_verdict="OFFENSIVE",
    )

    assert result is not None
    assert result["shares"] == 500.0
    assert result["risk_amount"] == 2500.0


def test_position_sizer_defensive_halves_size():
    """DEFENSIVE conditions should halve allowed trade risk."""
    from src.trade.sizer import calculate_position_size

    result = calculate_position_size(
        account_size=500_000,
        entry_price=100.0,
        stop_price=95.0,
        market_verdict="DEFENSIVE",
    )

    assert result is not None
    assert result["shares"] == 250.0


def test_position_sizer_rejects_stop_above_entry():
    """Invalid stops should be rejected."""
    from src.trade.sizer import calculate_position_size

    result = calculate_position_size(
        account_size=500_000,
        entry_price=100.0,
        stop_price=101.0,
    )

    assert result is None


def test_position_sizer_caps_at_max_position_pct():
    """Position size should respect the max position cap."""
    from src.trade.sizer import calculate_position_size

    result = calculate_position_size(
        account_size=500_000,
        entry_price=200.0,
        stop_price=199.0,
    )

    assert result is not None
    assert result["position_value"] <= 50_000.0


def test_trade_log_open_close_and_summary(tmp_db):
    """Open and close flow should persist trades and compute summary metrics."""
    from src.ingestion.store import init_db
    from src.trade.log import close_trade, get_closed_trades, get_open_trades, open_trade, summarize_closed_trades

    init_db()
    trade_id = open_trade(
        symbol="RELIANCE",
        setup_type="MOMENTUM_BURST",
        entry_date="2026-04-10",
        entry_price=100.0,
        shares=100,
        stop_price=95.0,
        target_price=115.0,
        notes="paper trade",
        grade="A",
    )

    open_trades = get_open_trades()
    assert len(open_trades) == 1
    assert int(open_trades.iloc[0]["id"]) == trade_id

    closed = close_trade(
        trade_id=trade_id,
        exit_date="2026-04-15",
        exit_price=115.0,
    )
    assert closed["status"] == config.TRADE_STATUS_CLOSED_WIN
    assert closed["r_multiple"] == 3.0

    closed_trades = get_closed_trades(last_n_days=0)
    assert len(closed_trades) == 1

    summary = summarize_closed_trades(last_n_days=0)
    assert summary["total_trades"] == 1.0
    assert summary["win_rate"] == 100.0
    assert summary["expectancy_r"] == 3.0


def test_build_open_trade_status_uses_latest_close(tmp_db):
    """Open trade status should include current close and unrealized P&L."""
    from src.ingestion.store import init_db, upsert_ohlcv
    from src.trade.log import build_open_trade_status, open_trade

    init_db()
    upsert_ohlcv(
        [
            {
                "symbol": "INFY",
                "date": "2026-04-10",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 500000,
            },
            {
                "symbol": "INFY",
                "date": "2026-04-11",
                "open": 101.0,
                "high": 103.0,
                "low": 100.0,
                "close": 104.0,
                "volume": 550000,
            },
        ]
    )

    open_trade(
        symbol="INFY",
        setup_type="TREND_INTENSITY",
        entry_date="2026-04-10",
        entry_price=100.0,
        shares=10,
        stop_price=95.0,
    )

    status_df = build_open_trade_status(as_of_date="2026-04-11")

    assert len(status_df) == 1
    assert float(status_df.iloc[0]["current_close"]) == 104.0
    assert float(status_df.iloc[0]["unrealized_pnl"]) == 40.0
