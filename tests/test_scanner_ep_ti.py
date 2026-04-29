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
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 1_000_000},
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


def test_detect_ep_exposes_research_feature_columns():
    """Episodic Pivot results should include research-oriented gap context fields."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    df = _make_ep_df(
        pre_closes=[100.0] * 70,
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 1_000_000},
        post_closes=[108.0, 109.0],
    )

    result = detect_episodic_pivot(df)
    row = result.iloc[0]

    assert "days_since_gap" in result.columns
    assert "gap_pct" in result.columns
    assert "gap_vol_ratio" in result.columns
    assert "gap_day_close_location_pct" in result.columns
    assert "prior_65d_run_pct" in result.columns
    assert "distance_to_52w_high_before_gap" in result.columns
    assert "holding_above_gap_open_days" in result.columns
    assert "gap_fill_pct" in result.columns
    assert "is_first_gap_in_6m" in result.columns
    assert row["days_since_gap"] >= 1
    assert row["gap_pct"] >= 4.0


def test_prepared_ep_features_preserve_detection_result():
    """Prepared-history path should preserve Episodic Pivot detection semantics."""
    from src.scanner.episodic_pivot import (
        detect_episodic_pivot,
        prepare_episodic_pivot_features,
    )

    df = _make_ep_df(
        pre_closes=[100.0] * 70,
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 1_000_000},
        post_closes=[108.0, 109.0],
    )

    direct_result = detect_episodic_pivot(df)
    prepared = prepare_episodic_pivot_features(df)
    prepared_result = detect_episodic_pivot(prepared[prepared["date"] <= prepared["date"].max()])

    assert len(direct_result) == 1
    assert len(prepared_result) == 1
    assert direct_result.iloc[0]["symbol"] == prepared_result.iloc[0]["symbol"]
    assert direct_result.iloc[0]["gap_pct"] == prepared_result.iloc[0]["gap_pct"]
    assert direct_result.iloc[0]["gap_vol_ratio"] == prepared_result.iloc[0]["gap_vol_ratio"]


def test_detect_ep_allows_same_day_gap_in_prepared_history():
    """Prepared-history EP detection should allow a qualifying gap on the latest row."""
    from src.scanner.episodic_pivot import (
        detect_episodic_pivot,
        prepare_episodic_pivot_features,
    )

    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 1_000_000},
        post_closes=[],
    )

    prepared = prepare_episodic_pivot_features(df)
    result = detect_episodic_pivot(prepared[prepared["date"] <= prepared["date"].max()])

    assert len(result) == 1
    assert result.iloc[0]["days_since_gap"] == 0
    assert result.iloc[0]["gap_pct"] >= 4.0


def test_ep_tier_a_plus_classification():
    """A large gap with very high volume on the same day → tier A+."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    # Gap of 9% with 5x volume on gap day, within 0 days → qualifies for A+
    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 109.0, "close": 112.0, "volume": 1_200_000},
        post_closes=[],
    )

    result = detect_episodic_pivot(df)

    assert len(result) == 1
    assert "ep_tier" in result.columns
    row = result.iloc[0]
    assert row["ep_tier"] == "A+"
    assert row["gap_pct"] >= 8.0
    assert row["days_since_gap"] <= 1


def test_ep_tier_b_classification():
    """A moderate gap with standard volume → tier B."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    # Gap of 6% with 3.5x volume — meets B thresholds but not A+
    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 106.0, "close": 108.0, "volume": 800_000},
        post_closes=[108.0],
    )

    result = detect_episodic_pivot(df)

    assert len(result) == 1
    assert "ep_tier" in result.columns
    assert result.iloc[0]["ep_tier"] == "B"


def test_ep_tier_column_always_present():
    """The ep_tier column should exist even when no candidates are found."""
    from src.scanner.episodic_pivot import detect_episodic_pivot

    df = _make_ep_df(
        pre_closes=[100.0] * 30,
        gap_day_data={"open": 101.0, "close": 101.5, "volume": 200_000},
        post_closes=[101.5],
    )

    result = detect_episodic_pivot(df)

    assert "ep_tier" in result.columns


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


def test_detect_ti_exposes_research_feature_columns():
    """Trend Intensity results should include research-oriented trend descriptors."""
    from src.scanner.trend_intensity import detect_trend_intensity
    import numpy as np

    count = 220
    closes = list(np.linspace(100, 160, count))
    volumes = [300_000] * (count - 1) + [450_000]
    dates = pd.date_range("2024-01-01", periods=count, freq="B")
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
    row = result.iloc[0]

    assert "distance_above_ma50_pct" in result.columns
    assert "distance_above_ma150_pct" in result.columns
    assert "distance_above_ma200_pct" in result.columns
    assert "ma150_above_ma200" in result.columns
    assert "ma200_rising_20d" in result.columns
    assert "within_25pct_of_52w_high" in result.columns
    assert "relative_strength_vs_benchmark_3m" in result.columns
    assert "trend_efficiency_ratio" in result.columns
    assert "pullback_depth_20d" in result.columns
    assert "vol_dryup_ratio_10d" in result.columns
    assert row["distance_above_ma50_pct"] > 0.0
    assert 0.0 <= row["trend_efficiency_ratio"] <= 1.0


def test_prepared_ti_features_preserve_detection_result():
    """Prepared-history path should preserve Trend Intensity detection semantics."""
    from src.scanner.trend_intensity import (
        detect_trend_intensity,
        prepare_trend_intensity_features,
    )
    import numpy as np

    count = 220
    closes = list(np.linspace(100, 160, count))
    volumes = [300_000] * (count - 1) + [450_000]
    dates = pd.date_range("2024-01-01", periods=count, freq="B")
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

    direct_result = detect_trend_intensity(df)
    prepared = prepare_trend_intensity_features(df)
    prepared_result = detect_trend_intensity(prepared[prepared["date"] == prepared["date"].max()])

    assert len(direct_result) == 1
    assert len(prepared_result) == 1
    assert direct_result.iloc[0]["symbol"] == prepared_result.iloc[0]["symbol"]
    assert direct_result.iloc[0]["pct_change"] == prepared_result.iloc[0]["pct_change"]
    assert direct_result.iloc[0]["volume_ratio"] == prepared_result.iloc[0]["volume_ratio"]


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
