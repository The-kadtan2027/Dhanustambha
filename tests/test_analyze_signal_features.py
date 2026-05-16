"""Tests for scripts/analyze_signal_features.py feature bucket analysis.

Covers:
- analyze_numeric_feature: quantile bucketing and metric computation
- analyze_boolean_feature: True/False split
- analyze_categorical_feature: per-category split
- compute_win_rate_spread: spread calculation with n-floor enforcement
- run_feature_analysis: end-to-end sorted results
- Missing columns handled gracefully
- Missing alpha columns handled gracefully
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.analyze_signal_features import (
    MIN_N_PER_BUCKET,
    PROMOTION_SPREAD_PP,
    analyze_boolean_feature,
    analyze_categorical_feature,
    analyze_numeric_feature,
    compute_win_rate_spread,
    run_feature_analysis,
)
from scripts.calibrate_thresholds import apply_feature_filters


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_signals(n: int = 80) -> pd.DataFrame:
    """Return a synthetic signals DataFrame with known outcome patterns.

    A strong directional pattern is forced on 'gap_pct':
    high gap_pct rows → positive return_5d,  low gap_pct rows → negative return_5d.
    This guarantees compute_win_rate_spread detects a spread >= PROMOTION_SPREAD_PP.
    """
    rng = np.random.default_rng(42)
    df = pd.DataFrame(
        {
            "return_5d": rng.normal(0.5, 3.0, n),
            "return_10d": rng.normal(1.0, 4.0, n),
            "alpha_5d": rng.normal(0.2, 2.0, n),
            "alpha_10d": rng.normal(0.5, 3.0, n),
            "mfe_5d": rng.uniform(0, 8, n),
            "mae_5d": rng.uniform(-5, 0, n),
            "market_verdict": rng.choice(["OFFENSIVE", "DEFENSIVE", "AVOID"], n),
            # numeric feature — high values should "win" more
            "gap_pct": rng.uniform(4, 15, n),
            # boolean feature
            "is_first_gap_in_6m": rng.choice([True, False], n),
            # categorical feature
            "ep_tier": rng.choice(["A+", "B"], n),
        }
    )
    # Force a strong pattern: high gap_pct → winner
    high_mask = df["gap_pct"] > df["gap_pct"].median()
    df.loc[high_mask, "return_5d"] = rng.uniform(3, 10, high_mask.sum())
    df.loc[~high_mask, "return_5d"] = rng.uniform(-8, -2, (~high_mask).sum())
    return df


# ── analyze_numeric_feature ───────────────────────────────────────────────────

def test_analyze_numeric_feature_returns_four_buckets():
    df = _make_signals(80)
    result = analyze_numeric_feature(df, "gap_pct")
    assert result is not None
    assert len(result) == 4
    assert "bucket" in result.columns
    assert "win_rate_5d_pct" in result.columns
    assert "n" in result.columns


def test_analyze_numeric_feature_returns_none_for_missing_column():
    df = _make_signals(20)
    result = analyze_numeric_feature(df, "nonexistent_column")
    assert result is None


def test_analyze_numeric_feature_metrics_are_finite():
    df = _make_signals(80)
    result = analyze_numeric_feature(df, "gap_pct")
    # All win rate values should be between 0 and 100
    for _, row in result.iterrows():
        if not np.isnan(row["win_rate_5d_pct"]):
            assert 0.0 <= row["win_rate_5d_pct"] <= 100.0


# ── compute_win_rate_spread ───────────────────────────────────────────────────

def test_compute_win_rate_spread_detects_strong_feature():
    df = _make_signals(80)
    bucket_df = analyze_numeric_feature(df, "gap_pct")
    spread = compute_win_rate_spread(bucket_df)
    # With the forced pattern, Q4 wins heavily and Q1 almost never wins
    assert spread >= PROMOTION_SPREAD_PP, (
        f"Expected spread >= {PROMOTION_SPREAD_PP}pp but got {spread}"
    )


def test_compute_win_rate_spread_ignores_small_n_buckets():
    """Buckets with fewer than MIN_N_PER_BUCKET signals must not count toward spread."""
    bucket_df = pd.DataFrame(
        {
            "bucket": ["Q1", "Q2", "Q3", "Q4"],
            "n": [MIN_N_PER_BUCKET - 1, 30, 30, 30],
            "win_rate_5d_pct": [95.0, 50.0, 50.0, 50.0],
        }
    )
    spread = compute_win_rate_spread(bucket_df)
    # Q1 is excluded (too few), so remaining three are all 50% → spread == 0
    assert spread == 0.0


def test_compute_win_rate_spread_returns_zero_if_only_one_qualifying_bucket():
    bucket_df = pd.DataFrame(
        {
            "bucket": ["Q1", "Q2"],
            "n": [MIN_N_PER_BUCKET - 1, MIN_N_PER_BUCKET - 1],
            "win_rate_5d_pct": [80.0, 40.0],
        }
    )
    spread = compute_win_rate_spread(bucket_df)
    assert spread == 0.0


# ── analyze_boolean_feature ───────────────────────────────────────────────────

def test_analyze_boolean_feature_returns_two_rows():
    df = _make_signals(60)
    result = analyze_boolean_feature(df, "is_first_gap_in_6m")
    assert result is not None
    assert len(result) == 2
    assert set(result["bucket"].astype(str)) == {"True", "False"}


def test_analyze_boolean_feature_returns_none_for_missing_column():
    df = _make_signals(20)
    result = analyze_boolean_feature(df, "missing_bool_col")
    assert result is None


# ── analyze_categorical_feature ───────────────────────────────────────────────

def test_analyze_categorical_feature_returns_all_values():
    df = _make_signals(60)
    result = analyze_categorical_feature(df, "ep_tier")
    assert result is not None
    assert set(result["bucket"]) == {"A+", "B"}


def test_analyze_categorical_feature_returns_none_for_missing_column():
    df = _make_signals(20)
    result = analyze_categorical_feature(df, "missing_cat_col")
    assert result is None


# ── run_feature_analysis ──────────────────────────────────────────────────────

def test_run_feature_analysis_returns_sorted_by_spread():
    df = _make_signals(80)
    results = run_feature_analysis(df, "episodic_pivot")
    spreads = [r["spread_pp"] for r in results]
    assert spreads == sorted(spreads, reverse=True)


def test_run_feature_analysis_returns_list_of_dicts():
    df = _make_signals(80)
    results = run_feature_analysis(df, "episodic_pivot")
    assert isinstance(results, list)
    for item in results:
        assert "feature" in item
        assert "spread_pp" in item
        assert "buckets" in item


def test_run_feature_analysis_handles_missing_alpha_columns():
    """Must not crash if alpha_* columns are absent (older signal CSVs)."""
    df = _make_signals(60)
    df = df.drop(columns=["alpha_5d", "alpha_10d"])
    results = run_feature_analysis(df, "episodic_pivot")
    assert isinstance(results, list)


def test_run_feature_analysis_momentum_burst_scanner():
    """Smoke test that MB scanner feature list also works end-to-end."""
    rng = np.random.default_rng(7)
    n = 80
    df = pd.DataFrame(
        {
            "return_5d": rng.normal(0.5, 3.0, n),
            "return_10d": rng.normal(1.0, 4.0, n),
            "pct_change": rng.uniform(5, 20, n),
            "volume_ratio": rng.uniform(1.5, 5.0, n),
            "close_location_pct": rng.uniform(20, 100, n),
            "market_verdict": rng.choice(["OFFENSIVE", "DEFENSIVE", "AVOID"], n),
            "mb_quality": rng.choice(["HIGH", "STANDARD"], n),
        }
    )
    results = run_feature_analysis(df, "momentum_burst")
    assert isinstance(results, list)
    feature_names = [r["feature"] for r in results]
    # mb_quality should be in results (categorical)
    assert "mb_quality" in feature_names


def test_apply_feature_filters_numeric():
    df = pd.DataFrame(
        {
            "gap_day_close_location_pct": [40.0, 55.0, 70.0, 80.0],
            "return_5d": [1.0, 2.0, 3.0, 4.0],
        }
    )
    result = apply_feature_filters(df, ["gap_day_close_location_pct:60"])
    assert len(result) == 2
    assert result["gap_day_close_location_pct"].min() >= 60.0


def test_apply_feature_filters_boolean():
    df = pd.DataFrame(
        {
            "is_first_gap_in_6m": [True, False, True, False],
            "return_5d": [1.0, 2.0, 3.0, 4.0],
        }
    )
    result = apply_feature_filters(df, ["is_first_gap_in_6m:True"])
    assert len(result) == 2
    assert result["is_first_gap_in_6m"].all()


def test_apply_feature_filters_categorical():
    df = pd.DataFrame(
        {
            "mb_quality": ["HIGH", "STANDARD", "high", "LOW"],
            "return_5d": [1.0, 2.0, 3.0, 4.0],
        }
    )
    result = apply_feature_filters(df, ["mb_quality:HIGH"])
    assert len(result) == 2
    assert set(result["mb_quality"].str.upper()) == {"HIGH"}


def test_apply_feature_filters_missing_column_skipped():
    df = pd.DataFrame({"return_5d": [1.0, 2.0]})
    result = apply_feature_filters(df, ["nonexistent_col:50"])
    assert len(result) == 2


def test_apply_feature_filters_none_returns_unchanged():
    df = pd.DataFrame({"return_5d": [1.0, 2.0, 3.0]})
    result = apply_feature_filters(df, None)
    assert len(result) == 3
