"""Tests for calibration ranking and report path helpers."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.calibrate_thresholds import (
    apply_feature_filters,
    build_filtered_result_row,
    build_output_paths,
    build_parser,
    limit_parameter_grid,
    rank_calibration_results,
)
from src.review.backtest import BacktestResult


def test_rank_calibration_results_uses_alpha_aware_priority():
    """Ranking should prefer stronger alpha and robustness before raw signal count."""
    result_df = pd.DataFrame(
        [
            {
                "param_set_id": "A",
                "median_alpha_5d": 1.0,
                "win_rate_5d": 60.0,
                "pct_hit_5pct_by_5d": 40.0,
                "avg_mae_5d": -4.0,
                "n_signals": 20,
            },
            {
                "param_set_id": "B",
                "median_alpha_5d": 1.5,
                "win_rate_5d": 55.0,
                "pct_hit_5pct_by_5d": 35.0,
                "avg_mae_5d": -5.0,
                "n_signals": 50,
            },
            {
                "param_set_id": "C",
                "median_alpha_5d": 1.5,
                "win_rate_5d": 55.0,
                "pct_hit_5pct_by_5d": 45.0,
                "avg_mae_5d": -3.0,
                "n_signals": 10,
            },
        ]
    )

    ranked = rank_calibration_results(result_df)

    assert ranked.iloc[0]["param_set_id"] == "C"
    assert ranked.iloc[1]["param_set_id"] == "B"
    assert ranked.iloc[2]["param_set_id"] == "A"


def test_build_output_paths_uses_summary_and_signals_suffixes():
    """Calibration outputs should use the final Stream D5 filename scheme."""
    summary_path, signals_path = build_output_paths(
        "2026-04-22",
        "momentum_burst",
        "NIFTY500",
    )

    assert summary_path.endswith("2026-04-22-momentum_burst-NIFTY500-summary.csv")
    assert signals_path.endswith("2026-04-22-momentum_burst-NIFTY500-signals.csv")


def test_limit_parameter_grid_caps_fast_run_size():
    """Fast-run mode should cap the grid size without reshaping parameter dictionaries."""
    grid = [{"id": 1}, {"id": 2}, {"id": 3}]

    limited = limit_parameter_grid(grid, max_param_sets=2)

    assert limited == [{"id": 1}, {"id": 2}]


def test_parser_accepts_summary_only_max_param_sets_and_feature_filters():
    """CLI parser should expose the fast-run calibration flags."""
    parser = build_parser()

    args = parser.parse_args(
        [
            "--scanner",
            "momentum_burst",
            "--summary-only",
            "--max-param-sets",
            "3",
            "--feature-filters",
            "gap_day_close_location_pct:60",
            "mb_quality:HIGH",
        ]
    )

    assert args.scanner == "momentum_burst"
    assert args.summary_only is True
    assert args.max_param_sets == 3
    assert args.feature_filters == ["gap_day_close_location_pct:60", "mb_quality:HIGH"]


def test_build_filtered_result_row_recomputes_summary_metrics():
    """Filtered calibration rows should rank on the filtered signal population."""
    signals = pd.DataFrame(
        {
            "return_5d": [-2.0, 5.0, 6.0],
            "alpha_5d": [-3.0, 4.0, 5.0],
            "mfe_5d": [1.0, 6.0, 7.0],
            "mae_5d": [-4.0, -1.0, -1.5],
            "gap_day_close_location_pct": [40.0, 65.0, 80.0],
            "market_verdict": ["OFFENSIVE", "OFFENSIVE", "DEFENSIVE"],
        }
    )
    result = BacktestResult(
        scanner_name="detect_episodic_pivot",
        universe="NIFTY500",
        start_date="2025-01-01",
        end_date="2025-01-31",
        params={"min_gap_pct": 4.0},
        param_set_id="ep:test",
        n_signals=len(signals),
        signal_results=signals,
    )
    filtered = apply_feature_filters(signals, ["gap_day_close_location_pct:60"])

    row = build_filtered_result_row(result, filtered, ["gap_day_close_location_pct:60"])

    assert row["raw_n_signals"] == 3
    assert row["n_signals"] == 2
    assert row["median_alpha_5d"] == 4.5
    assert row["win_rate_5d"] == 100.0


def test_apply_feature_filters_inclusive_range():
    """Range specs should keep rows inside low..high inclusive bounds."""
    df = pd.DataFrame(
        {
            "gap_day_close_location_pct": [40.0, 48.6, 52.0, 54.7, 80.0],
            "return_5d": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )

    result = apply_feature_filters(df, ["gap_day_close_location_pct:48.6..54.7"])

    assert result["gap_day_close_location_pct"].tolist() == [48.6, 52.0, 54.7]


def test_apply_feature_filters_comparison_operators():
    """Comparison specs should support <= and >= thresholds."""
    df = pd.DataFrame(
        {
            "gap_vol_ratio": [4.8, 4.9, 5.0, 27.0, 27.1],
            "return_5d": [1.0, 2.0, 3.0, 4.0, 5.0],
        }
    )

    low_result = apply_feature_filters(df, ["gap_vol_ratio<=4.9"])
    high_result = apply_feature_filters(df, ["gap_vol_ratio>=27.0"])

    assert low_result["gap_vol_ratio"].tolist() == [4.8, 4.9]
    assert high_result["gap_vol_ratio"].tolist() == [27.0, 27.1]
