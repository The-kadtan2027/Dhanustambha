"""Tests for the Momentum Burst scanner."""

import pandas as pd
import pytest


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
