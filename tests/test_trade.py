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
        entry_price=10.0,
        stop_price=5.0,
        market_verdict="OFFENSIVE",
    )

    assert result is not None
    assert result["shares"] == 2500.0
    assert result["risk_amount"] == 12500.0


def test_position_sizer_defensive_halves_size():
    """DEFENSIVE conditions should halve allowed trade risk."""
    from src.trade.sizer import calculate_position_size

    result = calculate_position_size(
        account_size=500_000,
        entry_price=10.0,
        stop_price=5.0,
        market_verdict="DEFENSIVE",
    )

    assert result is not None
    assert result["shares"] == 1250.0


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
    assert result["position_value"] <= 500_000 * config.TRADE_MAX_POSITION_PCT


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


def test_open_trade_rejects_stop_at_or_above_entry(tmp_db):
    """Shared trade creation should reject invalid risk geometry."""
    from src.ingestion.store import init_db
    from src.trade.log import open_trade

    init_db()

    with pytest.raises(ValueError, match="Stop price must be below entry price"):
        open_trade(
            symbol="FOO",
            setup_type="MOMENTUM_BURST",
            entry_date="2026-05-21",
            entry_price=100.0,
            shares=10,
            stop_price=100.0,
        )


def test_build_open_trade_status_uses_latest_close(tmp_db):
    """Open trade status should include current close, unrealized P&L, and action fields."""
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
                "high": 102.0,
                "low": 100.0,
                "close": 102.0,
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
    assert float(status_df.iloc[0]["current_close"]) == 102.0
    assert float(status_df.iloc[0]["unrealized_pnl"]) == 20.0
    assert float(status_df.iloc[0]["pct_gain"]) == 2.0
    assert int(status_df.iloc[0]["days_held"]) == 1
    assert status_df.iloc[0]["action_required"] == "NONE"


def test_open_trade_status_flags_breakeven_trail(tmp_db):
    """A trade up at least 5% with an underwater stop should request breakeven trail."""
    from src.ingestion.store import init_db, upsert_ohlcv
    from src.trade.log import build_open_trade_status, open_trade, update_stop_price

    init_db()
    upsert_ohlcv(
        [
            {
                "symbol": "RELIANCE",
                "date": "2026-04-10",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 500000,
            },
            {
                "symbol": "RELIANCE",
                "date": "2026-04-13",
                "open": 101.0,
                "high": 107.0,
                "low": 100.0,
                "close": 106.0,
                "volume": 600000,
            },
        ]
    )
    trade_id = open_trade(
        symbol="RELIANCE",
        setup_type="EP",
        entry_date="2026-04-10",
        entry_price=100.0,
        shares=10,
        stop_price=96.0,
    )

    status_df = build_open_trade_status(as_of_date="2026-04-13")

    assert float(status_df.iloc[0]["pct_gain"]) == 6.0
    assert status_df.iloc[0]["action_required"] == "TRAIL_TO_BREAKEVEN"

    update_result = update_stop_price(trade_id=trade_id, stop_price=100.0)
    assert update_result["old_stop_price"] == 96.0
    assert update_result["new_stop_price"] == 100.0

    updated_status = build_open_trade_status(as_of_date="2026-04-13")
    assert float(updated_status.iloc[0]["stop_price"]) == 100.0
    assert updated_status.iloc[0]["action_required"] == "NONE"


def test_open_trade_status_flags_stop_loss_hit(tmp_db):
    """A trade with current price at or below stop should request immediate close."""
    from src.ingestion.store import init_db, upsert_ohlcv
    from src.trade.log import build_open_trade_status, open_trade

    init_db()
    upsert_ohlcv(
        [
            {
                "symbol": "ERIS",
                "date": "2026-05-20",
                "open": 1460.0,
                "high": 1470.0,
                "low": 1450.0,
                "close": 1460.3,
                "volume": 500000,
            },
            {
                "symbol": "ERIS",
                "date": "2026-05-21",
                "open": 1435.0,
                "high": 1440.0,
                "low": 1387.0,
                "close": 1391.1,
                "volume": 700000,
            },
        ]
    )
    open_trade(
        symbol="ERIS",
        setup_type="EPISODIC_PIVOT",
        entry_date="2026-05-20",
        entry_price=1460.3,
        shares=22,
        stop_price=1429.65,
    )

    status_df = build_open_trade_status(as_of_date="2026-05-21")

    assert float(status_df.iloc[0]["current_close"]) == 1391.1
    assert status_df.iloc[0]["action_required"] == "STOP_LOSS_HIT"


def test_open_trade_status_flags_advanced_trailing_tiers(tmp_db):
    """A trade up 8% should request TRAIL_TO_3PCT, up 11% should request TRAIL_TO_7_5PCT."""
    from src.ingestion.store import init_db, upsert_ohlcv
    from src.trade.log import build_open_trade_status, open_trade

    init_db()
    upsert_ohlcv(
        [
            {"symbol": "TCS", "date": "2026-05-01", "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 500},
            {"symbol": "TCS", "date": "2026-05-02", "open": 100.0, "high": 109.0, "low": 99.0, "close": 108.0, "volume": 500},
            {"symbol": "TCS", "date": "2026-05-03", "open": 100.0, "high": 112.0, "low": 99.0, "close": 111.0, "volume": 500},
        ]
    )
    open_trade(
        symbol="TCS",
        setup_type="EP",
        entry_date="2026-05-01",
        entry_price=100.0,
        shares=10,
        stop_price=96.0,
    )

    # 8.0% gain
    status_df2 = build_open_trade_status(as_of_date="2026-05-02")
    assert status_df2.iloc[0]["action_required"] == "TRAIL_TO_3PCT"

    # 11.0% gain
    status_df3 = build_open_trade_status(as_of_date="2026-05-03")
    assert status_df3.iloc[0]["action_required"] == "TRAIL_TO_7_5PCT"



def test_open_trade_status_flags_time_exit_after_twenty_trading_days(tmp_db):
    """A trade held for 20 stored trading sessions should request a time exit."""
    from src.ingestion.store import init_db, upsert_ohlcv
    from src.trade.log import build_open_trade_status, open_trade

    init_db()
    rows = []
    for day in range(1, 22):
        rows.append(
            {
                "symbol": "TCS",
                "date": f"2026-04-{day:02d}",
                "open": 100.0,
                "high": 103.0,
                "low": 99.0,
                "close": 102.0,
                "volume": 500000,
            }
        )
    upsert_ohlcv(rows)
    open_trade(
        symbol="TCS",
        setup_type="TREND_INTENSITY",
        entry_date="2026-04-01",
        entry_price=100.0,
        shares=10,
        stop_price=98.0,
    )

    status_df = build_open_trade_status(as_of_date="2026-04-21")

    assert int(status_df.iloc[0]["days_held"]) == 20
    assert status_df.iloc[0]["action_required"] == "TIME_EXIT"
