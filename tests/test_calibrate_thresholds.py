"""Tests for calibration ranking and report path helpers."""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.calibrate_thresholds import (
    build_output_paths,
    build_parser,
    limit_parameter_grid,
    rank_calibration_results,
)


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


def test_parser_accepts_summary_only_and_max_param_sets():
    """CLI parser should expose the fast-run calibration flags."""
    parser = build_parser()

    args = parser.parse_args(
        ["--scanner", "momentum_burst", "--summary-only", "--max-param-sets", "3"]
    )

    assert args.scanner == "momentum_burst"
    assert args.summary_only is True
    assert args.max_param_sets == 3
