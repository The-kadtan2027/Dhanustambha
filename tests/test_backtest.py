"""Tests for scanner backtesting and calibration helpers."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.review.backtest import build_parameter_grid, run_backtest


def test_backtest_runs_on_synthetic_data():
    """Backtest should emit signals and summary metrics on synthetic momentum data."""
    from src.scanner.momentum_burst import detect_momentum_burst

    rows = []
    dates = pd.date_range("2025-01-01", periods=40, freq="B")
    for symbol in ["AAA", "BBB"]:
        closes = [100.0] * 36 + [100.0, 100.0, 106.0, 108.0]
        volumes = [300_000] * 38 + [800_000, 900_000]
        for idx, trading_date in enumerate(dates):
            close = closes[idx]
            rows.append(
                {
                    "symbol": symbol,
                    "date": trading_date,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "volume": volumes[idx],
                }
            )

    history = pd.DataFrame(rows)
    result = run_backtest(
        scanner_fn=detect_momentum_burst,
        universe="NIFTY50_TEST",
        start_date="2025-02-01",
        end_date="2025-02-28",
        price_history=history,
    )

    assert result.n_signals > 0
    assert "return_5d" in result.signal_results.columns
    assert result.avg_return_5d >= 0.0


def test_forward_return_correct():
    """Forward return calculation should match known close values."""
    def fake_scanner(df, **params):
        latest = df["date"].max()
        latest_rows = df[df["date"] == latest]
        return pd.DataFrame(
            [
                {
                    "symbol": latest_rows.iloc[0]["symbol"],
                    "setup_type": "TEST",
                    "score": 1.0,
                }
            ]
        )

    dates = pd.date_range("2025-01-01", periods=30, freq="B")
    closes = np.linspace(100, 130, len(dates))
    history = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates),
            "date": dates,
            "open": closes,
            "high": closes + 1,
            "low": closes - 1,
            "close": closes,
            "volume": [300_000] * len(dates),
        }
    )

    result = run_backtest(
        scanner_fn=fake_scanner,
        universe="NIFTY50_TEST",
        start_date="2025-01-15",
        end_date="2025-01-15",
        price_history=history,
    )

    signal = result.signal_results.iloc[0]
    expected = round((closes[15] - closes[10]) / closes[10] * 100, 2)
    assert signal["return_5d"] == expected


def test_build_parameter_grid_shape():
    """Calibration grids should return multiple parameter combinations."""
    result = build_parameter_grid("momentum_burst")

    assert len(result) > 1
    assert {"min_pct", "min_vol_ratio"} <= set(result[0].keys())
