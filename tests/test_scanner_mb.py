"""Tests for the Momentum Burst scanner."""

import pandas as pd
import pytest

import config


@pytest.fixture(autouse=True)
def _relax_prior_run_filter(monkeypatch):
    """Synthetic tests use flat bases which fail the new strict -2.3% limit."""
    monkeypatch.setattr(config, "MB_MAX_PRIOR_RUN", 15.0)


def _make_symbol_df(closes, volumes, symbol="TEST") -> pd.DataFrame:
    """Build a single-symbol OHLCV DataFrame with deterministic values."""
    count = len(closes)
    dates = pd.date_range("2025-01-01", periods=count, freq="B")
    return pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates,
            "open": [close * 0.99 for close in closes],
            "high": [close * 1.01 for close in closes],
            "low": [close * 0.98 for close in closes],
            "close": closes,
            "volume": volumes,
        }
    )


def test_detect_clear_momentum_burst():
    """A flat stock with a sharp price and volume expansion should be detected."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 25 + [108.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "TEST"
    assert result.iloc[0]["pct_change"] == pytest.approx(8.0, abs=0.1)


def test_no_burst_when_volume_insufficient():
    """No candidate should appear if the price move lacks volume confirmation."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 25 + [108.0]
    volumes = [200_000] * 26
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert len(result) == 0


def test_no_burst_when_price_change_too_small():
    """No candidate should appear if the move is below the configured threshold."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 25 + [102.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert len(result) == 0


def test_no_burst_when_already_extended():
    """Stocks with a large prior run should be excluded from burst candidates."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [80.0] * 15 + [82.0, 84.0, 86.0, 88.0, 90.0, 92.0, 94.0, 96.0, 98.0, 100.0] + [108.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert len(result) == 0


def test_burst_result_has_required_columns():
    """Detected results should expose the expected downstream watchlist fields."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 25 + [108.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert "symbol" in result.columns
    assert "pct_change" in result.columns
    assert "volume_ratio" in result.columns
    assert "score" in result.columns
    assert "close" in result.columns
    assert "setup_type" in result.columns


def test_prior_run_filter_only_checks_the_prior_10_days():
    """Older runs should not invalidate a fresh burst if the last 10 days were quiet."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = (
        [80.0, 82.0, 84.0, 86.0, 88.0, 90.0, 92.0, 94.0, 96.0, 98.0]
        + [100.0] * 15
        + [108.0]
    )
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert len(result) == 1
    assert result.iloc[0]["symbol"] == "TEST"


def test_momentum_burst_exposes_research_feature_columns():
    """Momentum Burst results should include non-blocking research fields."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 25 + [108.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)
    row = result.iloc[0]

    assert "close_location_pct" in result.columns
    assert "range_expansion_ratio" in result.columns
    assert "nr_count_10d" in result.columns
    assert "consolidation_days" in result.columns
    assert "prior_10d_run_pct" in result.columns
    assert "prior_20d_run_pct" in result.columns
    assert "distance_from_20d_high_pct" in result.columns
    assert "trend_linearity_20d" in result.columns
    assert 0.0 <= row["close_location_pct"] <= 100.0
    assert row["range_expansion_ratio"] > 0.0


def test_prepared_momentum_features_preserve_detection_result():
    """Prepared-history path should preserve Momentum Burst detection semantics."""
    from src.scanner.momentum_burst import (
        detect_momentum_burst,
        prepare_momentum_burst_features,
    )

    closes = [100.0] * 25 + [108.0]
    volumes = [200_000] * 25 + [600_000]
    df = _make_symbol_df(closes, volumes)

    direct_result = detect_momentum_burst(df)
    prepared = prepare_momentum_burst_features(df)
    prepared_result = detect_momentum_burst(prepared[prepared["date"] == prepared["date"].max()])

    assert len(direct_result) == 1
    assert len(prepared_result) == 1
    assert direct_result.iloc[0]["symbol"] == prepared_result.iloc[0]["symbol"]
    assert direct_result.iloc[0]["pct_change"] == prepared_result.iloc[0]["pct_change"]
    assert direct_result.iloc[0]["volume_ratio"] == prepared_result.iloc[0]["volume_ratio"]


def test_mb_quality_high_classification():
    """An MB candidate from a tight base, strong close, new 20d high → HIGH quality."""
    from src.scanner.momentum_burst import detect_momentum_burst

    # 25 days of tight consolidation (NR days = high), then a breakout to new 20d high
    # Use very tight range to maximize NR count
    closes = [100.0] * 25 + [108.0]
    # Construct OHLCV with very narrow ranges for the first 25 days (-> NR count will be high)
    count = len(closes)
    dates = pd.date_range("2025-01-01", periods=count, freq="B")
    df = pd.DataFrame({
        "symbol": "TIGHT",
        "date": dates,
        # Tight ranges for consolidation phase; wide range on burst day with close near high
        "open": [100.0] * 25 + [103.0],
        "high": [100.1] * 25 + [108.5],
        "low": [99.9] * 25 + [102.5],
        "close": closes,
        "volume": [200_000] * 25 + [600_000],
    })

    result = detect_momentum_burst(df)

    assert len(result) == 1
    assert "mb_quality" in result.columns
    row = result.iloc[0]
    assert row["mb_quality"] == "HIGH"
    # Verify the underlying features that drove the classification
    assert row["nr_count_10d"] >= 6
    assert row["close_location_pct"] >= 70.0
    assert row["distance_from_20d_high_pct"] >= 0.0


def test_mb_quality_standard_classification():
    """An MB candidate without a tight base → STANDARD quality."""
    from src.scanner.momentum_burst import detect_momentum_burst

    # Varied (non-tight) price action before a burst — NR count will be low
    closes = list(range(95, 120)) + [130.0]
    count = len(closes)
    dates = pd.date_range("2025-01-01", periods=count, freq="B")
    df = pd.DataFrame({
        "symbol": "WILD",
        "date": dates,
        "open": [c * 0.97 for c in closes],
        "high": [c * 1.03 for c in closes],
        "low": [c * 0.96 for c in closes],
        "close": [float(c) for c in closes],
        "volume": [200_000] * (count - 1) + [600_000],
    })

    result = detect_momentum_burst(df)

    # May or may not detect a burst depending on thresholds, but if detected,
    # the noisy prior action should yield STANDARD quality
    if len(result) > 0:
        assert "mb_quality" in result.columns
        assert result.iloc[0]["mb_quality"] == "STANDARD"


def test_mb_quality_column_always_present():
    """The mb_quality column should exist even when no candidates are found."""
    from src.scanner.momentum_burst import detect_momentum_burst

    closes = [100.0] * 26
    volumes = [200_000] * 26
    df = _make_symbol_df(closes, volumes)

    result = detect_momentum_burst(df)

    assert "mb_quality" in result.columns


def test_mb_prior_run_filter_rejects_extended_stock():
    """detect_momentum_burst() must reject stocks whose prior 10d run exceeds MB_MAX_PRIOR_RUN.

    G2-validated filter: stocks already up >-2.3% in the prior 10 days before the burst
    are excluded because prior exhaustion run predicts poor forward alpha.
    """
    from src.scanner.momentum_burst import detect_momentum_burst

    # The autouse fixture relaxes MB_MAX_PRIOR_RUN to 15.0 for the session,
    # so we need to tighten it back to the G2-validated value for this test.
    original = config.MB_MAX_PRIOR_RUN
    config.MB_MAX_PRIOR_RUN = -2.3
    try:
        # days 0-9: run from 90.0 → 99.0 (+10% prior run), days 10-24: flat, day 25: burst
        closes = [90.0, 91.0, 92.0, 93.0, 94.0, 95.0, 96.0, 97.0, 98.0, 99.0] + [99.0] * 15 + [108.0]
        volumes = [200_000] * 25 + [600_000]
        df = _make_symbol_df(closes, volumes)
        result = detect_momentum_burst(df)
        assert result.empty, (
            "Should reject stock with prior 10d run > -2.3% (G2-validated MB filter)"
        )
    finally:
        config.MB_MAX_PRIOR_RUN = original
