"""Tests for Episodic Pivot and Trend Intensity scanners."""

import pandas as pd


def _make_ep_df(pre_closes, gap_day_data, post_closes=None) -> pd.DataFrame:
    """Build a single-symbol DataFrame that simulates a gap-up event."""
    post_closes = post_closes or []
    closes = pre_closes + [gap_day_data["close"]] + post_closes
    volumes = (
        [200_000] * len(pre_closes)
        + [gap_day_data["volume"]]
        + [200_000] * len(post_closes)
    )
    count = len(closes)
    dates = pd.date_range("2025-01-01", periods=count, freq="B")

    return pd.DataFrame(
        {
            "symbol": "GAPTEST",
            "date": dates,
            "open": [closes[0]] * len(pre_closes)
            + [gap_day_data["open"]]
            + [gap_day_data["close"]] * len(post_closes),
            "high": [close * 1.01 for close in closes],
            "low": [close * 0.99 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_detect_ep_valid_gap():
    """A sufficiently large, high-volume gap that holds should be detected."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 800_000},
        post_closes=[108.0, 109.0],
    )

    result = detect_episodic_pivot(df)

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "GAPTEST"


def test_detect_ep_gap_too_small():
    """A small gap should not qualify as an Episodic Pivot."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 102.0, "close": 103.0, "volume": 800_000},
        post_closes=[103.0],
    )

    result = detect_episodic_pivot(df)

    assert len(result) == 0


def test_detect_ti_valid_trend():
    """A steady low-volatility uptrend breaking higher should be detected."""
    from src.scanner.trend_intensity import detect_trend_intensity
    import numpy as np

    count = 60
    closes = list(np.linspace(100, 115, count))
    volumes = [300_000] * (count - 1) + [450_000]
    dates = pd.date_range("2025-01-01", periods=count, freq="B")
    df = pd.DataFrame(
        {
            "symbol": "TREND",
            "date": dates,
            "open": [close * 0.995 for close in closes],
            "high": [close * 1.005 for close in closes],
            "low": [close * 0.990 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )

    result = detect_trend_intensity(df)

    assert len(result) == 1


def test_detect_ti_no_trend_below_ma50():
    """A downtrend should not qualify as Trend Intensity."""
    from src.scanner.trend_intensity import detect_trend_intensity
    import numpy as np

    count = 60
    closes = list(np.linspace(115, 100, count))
    volumes = [300_000] * count
    dates = pd.date_range("2025-01-01", periods=count, freq="B")
    df = pd.DataFrame(
        {
            "symbol": "DOWN",
            "date": dates,
            "open": [close * 0.995 for close in closes],
            "high": [close * 1.005 for close in closes],
            "low": [close * 0.990 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )

    result = detect_trend_intensity(df)

    assert len(result) == 0
