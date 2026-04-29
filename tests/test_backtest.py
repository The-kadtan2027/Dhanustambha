"""Tests for scanner backtesting and calibration helpers."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.review.backtest import build_parameter_grid, run_backtest


def test_backtest_runs_on_synthetic_data():
    """Backtest should emit richer signal rows and summary metrics on synthetic data."""
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
    benchmark_history = pd.DataFrame(
        {
            "symbol": ["^NSEI"] * len(dates),
            "date": dates,
            "open": np.linspace(1000, 1040, len(dates)),
            "high": np.linspace(1005, 1045, len(dates)),
            "low": np.linspace(995, 1035, len(dates)),
            "close": np.linspace(1000, 1040, len(dates)),
            "volume": [1_000_000] * len(dates),
        }
    )
    result = run_backtest(
        scanner_fn=detect_momentum_burst,
        universe="NIFTY50_TEST",
        start_date="2025-02-01",
        end_date="2025-02-28",
        price_history=history,
        benchmark_history=benchmark_history,
    )

    assert result.n_signals > 0
    assert "param_set_id" in result.signal_results.columns
    assert "scanner_name" in result.signal_results.columns
    assert "return_1d" in result.signal_results.columns
    assert "return_3d" in result.signal_results.columns
    assert "return_5d" in result.signal_results.columns
    assert "mfe_3d" in result.signal_results.columns
    assert "mae_5d" in result.signal_results.columns
    assert "nifty_return_5d" in result.signal_results.columns
    assert "alpha_5d" in result.signal_results.columns
    assert "failed_to_gain_by_3d" in result.signal_results.columns
    assert "hit_5pct_by_5d" in result.signal_results.columns
    assert result.to_dict()["avg_return_3d"] >= 0.0
    assert result.avg_return_5d >= 0.0
    assert "avg_alpha_5d" in result.to_dict()
    assert "median_return_5d" in result.to_dict()


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
    benchmark_history = pd.DataFrame(
        {
            "symbol": ["^NSEI"] * len(dates),
            "date": dates,
            "open": closes * 0.5,
            "high": closes * 0.5 + 1,
            "low": closes * 0.5 - 1,
            "close": np.linspace(200, 215, len(dates)),
            "volume": [1_000_000] * len(dates),
        }
    )

    result = run_backtest(
        scanner_fn=fake_scanner,
        universe="NIFTY50_TEST",
        start_date="2025-01-15",
        end_date="2025-01-15",
        price_history=history,
        benchmark_history=benchmark_history,
    )

    signal = result.signal_results.iloc[0]
    expected = round((closes[15] - closes[10]) / closes[10] * 100, 2)
    benchmark_closes = benchmark_history["close"].to_numpy()
    expected_benchmark = round((benchmark_closes[15] - benchmark_closes[10]) / benchmark_closes[10] * 100, 2)
    assert signal["return_5d"] == expected
    assert signal["nifty_return_5d"] == expected_benchmark
    assert signal["alpha_5d"] == round(expected - expected_benchmark, 2)


def test_excursion_and_failure_metrics_use_forward_highs_and_lows():
    """Excursion metrics should use the forward window after the entry date."""

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

    dates = pd.date_range("2025-01-01", periods=15, freq="B")
    closes = [100.0] * 10 + [100.0, 102.0, 104.0, 103.0, 105.0]
    highs = [101.0] * 10 + [100.0, 103.0, 107.0, 104.0, 106.0]
    lows = [99.0] * 10 + [100.0, 99.0, 98.0, 101.0, 102.0]
    history = pd.DataFrame(
        {
            "symbol": ["AAA"] * len(dates),
            "date": dates,
            "open": closes,
            "high": highs,
            "low": lows,
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
        benchmark_history=pd.DataFrame(),
        forward_days=(3, 5),
    )

    signal = result.signal_results.iloc[0]
    assert signal["mfe_3d"] == 7.0
    assert signal["mae_3d"] == -2.0
    assert bool(signal["failed_to_gain_by_3d"]) is False
    assert bool(signal["hit_2pct_by_3d"]) is True


def test_backtest_attaches_breadth_context_and_regime_summary():
    """Backtest rows should carry stored breadth context and expose regime summaries."""

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
    breadth_history = pd.DataFrame(
        {
            "date": [dates[10]],
            "pct_above_ma20": [60.0],
            "pct_above_ma50": [55.0],
            "new_highs_52w": [10],
            "new_lows_52w": [2],
            "up_volume_ratio": [0.7],
            "advancing": [80],
            "declining": [20],
            "verdict": ["OFFENSIVE"],
        }
    )

    result = run_backtest(
        scanner_fn=fake_scanner,
        universe="NIFTY50_TEST",
        start_date="2025-01-15",
        end_date="2025-01-15",
        price_history=history,
        benchmark_history=pd.DataFrame(),
        breadth_history=breadth_history,
    )

    signal = result.signal_results.iloc[0]
    assert signal["market_verdict"] == "OFFENSIVE"
    assert signal["pct_above_ma20_on_day"] == 60.0
    assert signal["advancing_on_day"] == 80
    assert result.to_dict()["signals_offensive"] == 1
    assert "offensive_win_rate_5d" in result.to_dict()


def test_backtest_builds_local_benchmark_proxy_when_external_benchmark_missing():
    """Backtest should derive a local equal-weight benchmark proxy if no benchmark rows exist."""

    def fake_scanner(df, **params):
        latest = df["date"].max()
        latest_rows = df[df["date"] == latest]
        return pd.DataFrame(
            [
                {
                    "symbol": "AAA",
                    "setup_type": "TEST",
                    "score": 1.0,
                }
            ]
        )

    dates = pd.date_range("2025-01-01", periods=8, freq="B")
    rows = []
    aaa_closes = [100, 101, 102, 103, 104, 105, 106, 107]
    bbb_closes = [100, 100, 101, 101, 102, 103, 103, 104]
    for symbol, closes in {"AAA": aaa_closes, "BBB": bbb_closes}.items():
        for current_date, close in zip(dates, closes):
            rows.append(
                {
                    "symbol": symbol,
                    "date": current_date,
                    "open": float(close),
                    "high": float(close + 1),
                    "low": float(close - 1),
                    "close": float(close),
                    "volume": 100_000,
                }
            )
    history = pd.DataFrame(rows)

    result = run_backtest(
        scanner_fn=fake_scanner,
        universe="NIFTY50_TEST",
        start_date=dates[4].date().isoformat(),
        end_date=dates[4].date().isoformat(),
        price_history=history,
        benchmark_history=pd.DataFrame(),
    )

    signal = result.signal_results.iloc[0]
    assert pd.notna(signal["nifty_return_3d"])
    assert pd.notna(signal["alpha_3d"])
    assert signal["nifty_return_3d"] != signal["return_3d"]


def test_build_parameter_grid_shape():
    """Calibration grids should return multiple parameter combinations."""
    result = build_parameter_grid("momentum_burst")

    assert len(result) > 1
    assert {"min_pct", "min_vol_ratio", "max_prior_run"} <= set(result[0].keys())


def test_backtest_ep_detects_same_day_gap_with_prepared_history():
    """EP backtests should detect qualifying same-day gaps when using prepared history."""
    from src.review.backtest import prepare_scanner_history
    from src.scanner.episodic_pivot import detect_episodic_pivot

    dates = pd.date_range("2025-01-01", periods=35, freq="B")
    rows = []
    closes = [100.0] * 30 + [108.0, 109.0, 110.0, 111.0, 112.0]
    opens = [100.0] * 30 + [106.0, 108.0, 109.0, 110.0, 111.0]
    volumes = [200_000] * 30 + [1_000_000, 200_000, 200_000, 200_000, 200_000]
    for idx, trading_date in enumerate(dates):
        rows.append(
            {
                "symbol": "GAPTEST",
                "date": trading_date,
                "open": opens[idx],
                "high": closes[idx] * 1.01,
                "low": closes[idx] * 0.99,
                "close": closes[idx],
                "volume": volumes[idx],
            }
        )
    history = pd.DataFrame(rows)
    prepared = prepare_scanner_history(detect_episodic_pivot, history)

    result = run_backtest(
        scanner_fn=detect_episodic_pivot,
        universe="NIFTY50_TEST",
        start_date=dates[30].date().isoformat(),
        end_date=dates[30].date().isoformat(),
        price_history=history,
        benchmark_history=pd.DataFrame(),
        prepared_history_by_date=prepared,
        params={"min_gap_pct": 4.0, "min_gap_vol_ratio": 3.0, "max_days_since_gap": 1},
    )

    assert result.n_signals == 1
    assert result.signal_results.iloc[0]["symbol"] == "GAPTEST"
    assert result.signal_results.iloc[0]["days_since_gap"] == 0


def test_build_parameter_grid_matches_stream_d6_ranges():
    """Expanded Stream D6 parameter grids should include the planned edge values."""
    mb_grid = build_parameter_grid("momentum_burst")
    ep_grid = build_parameter_grid("episodic_pivot")
    ti_grid = build_parameter_grid("trend_intensity")

    assert len(mb_grid) == 5 * 5 * 4
    assert {"min_pct": 4.0, "min_vol_ratio": 1.3, "max_prior_run": 8.0} in mb_grid
    assert {"min_pct": 8.0, "min_vol_ratio": 2.5, "max_prior_run": 15.0} in mb_grid

    assert len(ep_grid) == 4 * 4 * 4
    assert {"min_gap_pct": 4.0, "min_gap_vol_ratio": 3.0, "max_days_since_gap": 1} in ep_grid
    assert {"min_gap_pct": 8.0, "min_gap_vol_ratio": 6.0, "max_days_since_gap": 5} in ep_grid

    assert len(ti_grid) == 4 * 4 * 3
    assert {"max_atr_pct": 0.02, "min_days_above_ma50": 30, "min_vol_ratio": 1.2} in ti_grid
    assert {"max_atr_pct": 0.05, "min_days_above_ma50": 45, "min_vol_ratio": 1.5} in ti_grid
