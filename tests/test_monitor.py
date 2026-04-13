"""Tests for market breadth computation and verdict logic."""

import numpy as np
import pandas as pd


def _make_ohlcv(n_symbols: int, n_days: int, pct_above_ma: float) -> pd.DataFrame:
    """Build a synthetic multi-symbol OHLCV DataFrame for breadth tests."""
    rows = []
    symbols = [f"SYM{i:03d}" for i in range(n_symbols)]
    dates = pd.date_range("2025-01-01", periods=n_days, freq="B")
    n_above = int(n_symbols * pct_above_ma)

    for index, symbol in enumerate(symbols):
        if index < n_above:
            closes = np.linspace(100, 120, n_days)
        else:
            closes = np.linspace(120, 100, n_days)

        for day_index, current_date in enumerate(dates):
            rows.append(
                {
                    "symbol": symbol,
                    "date": current_date,
                    "open": closes[day_index] - 1,
                    "high": closes[day_index] + 1,
                    "low": closes[day_index] - 2,
                    "close": closes[day_index],
                    "volume": 300_000 + (day_index * 1000),
                }
            )

    return pd.DataFrame(rows)


def test_compute_breadth_returns_expected_keys():
    """compute_breadth should return all expected metric keys."""
    from src.monitor.breadth import compute_breadth

    df = _make_ohlcv(100, 60, 0.60)
    result = compute_breadth(df)

    assert "pct_above_ma20" in result
    assert "pct_above_ma50" in result
    assert "new_highs_52w" in result
    assert "new_lows_52w" in result
    assert "up_volume_ratio" in result
    assert "advancing" in result
    assert "declining" in result


def test_compute_breadth_offensive_when_majority_above_ma():
    """compute_breadth should reflect strong participation in rising symbols."""
    from src.monitor.breadth import compute_breadth

    df = _make_ohlcv(100, 60, 0.65)
    metrics = compute_breadth(df)

    assert metrics["pct_above_ma20"] > 55.0


def test_verdict_offensive():
    """compute_verdict should return OFFENSIVE for strong breadth."""
    from src.monitor.verdict import compute_verdict

    metrics = {
        "pct_above_ma20": 60.0,
        "pct_above_ma50": 55.0,
        "new_highs_52w": 60,
        "new_lows_52w": 10,
        "up_volume_ratio": 0.65,
        "advancing": 300,
        "declining": 150,
    }

    assert compute_verdict(metrics) == "OFFENSIVE"


def test_verdict_defensive():
    """compute_verdict should return DEFENSIVE for mixed but positive breadth."""
    from src.monitor.verdict import compute_verdict

    metrics = {
        "pct_above_ma20": 50.0,
        "pct_above_ma50": 45.0,
        "new_highs_52w": 30,
        "new_lows_52w": 20,
        "up_volume_ratio": 0.52,
        "advancing": 220,
        "declining": 200,
    }

    assert compute_verdict(metrics) == "DEFENSIVE"


def test_verdict_avoid():
    """compute_verdict should return AVOID for weak breadth."""
    from src.monitor.verdict import compute_verdict

    metrics = {
        "pct_above_ma20": 35.0,
        "pct_above_ma50": 30.0,
        "new_highs_52w": 10,
        "new_lows_52w": 80,
        "up_volume_ratio": 0.35,
        "advancing": 120,
        "declining": 380,
    }

    assert compute_verdict(metrics) == "AVOID"
