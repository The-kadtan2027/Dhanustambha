#!/usr/bin/env python3
"""Run scanner parameter calibration against stored OHLCV history."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from typing import Dict, List

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.store import get_breadth_range, get_ohlcv_range
from src.ingestion.symbols import get_universe_symbols
from src.review.backtest import (
    BacktestResult,
    build_parameter_grid,
    get_scanner,
    _compute_summary_metrics,
    prepare_scanner_history,
    run_backtest,
)


def _format_seconds(seconds: float) -> str:
    """Return a compact human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, remainder = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {remainder:.1f}s"
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours)}h {int(minutes)}m {remainder:.1f}s"


def rank_calibration_results(result_df: pd.DataFrame) -> pd.DataFrame:
    """Return calibration summary rows ranked by alpha-aware robustness criteria."""
    ranking_columns = [
        "median_alpha_5d",
        "win_rate_5d",
        "pct_hit_5pct_by_5d",
        "avg_mae_5d",
        "n_signals",
    ]
    working = result_df.copy()
    for column in ranking_columns:
        if column not in working.columns:
            working[column] = 0.0
    return working.sort_values(
        ranking_columns,
        ascending=[False, False, False, True, False],
    ).reset_index(drop=True)


def build_output_paths(run_date: str, scanner: str, universe: str, label: str | None = None) -> tuple[str, str]:
    """Return summary and signal output paths for one calibration run."""
    base_name = label if label else f"{run_date}-{scanner}-{universe}"
    summary_path = os.path.join(
        config.BACKTEST_OUTPUT_DIR,
        f"{base_name}-summary.csv",
    )
    signals_path = os.path.join(
        config.BACKTEST_OUTPUT_DIR,
        f"{base_name}-signals.csv",
    )
    return summary_path, signals_path


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for calibration runs."""
    parser = argparse.ArgumentParser(description="Calibrate scanner thresholds")
    parser.add_argument("--scanner", default="momentum_burst")
    parser.add_argument("--universe", default=config.UNIVERSE)
    parser.add_argument(
        "--start-date",
        default=(pd.Timestamp.today() - pd.DateOffset(years=config.BACKTEST_YEARS)).date().isoformat(),
    )
    parser.add_argument("--end-date", default=pd.Timestamp.today().date().isoformat())
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Skip writing the full signal-level CSV and only save the ranked summary report",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="Optional label to override output filename",
    )
    parser.add_argument(
        "--max-param-sets",
        type=int,
        default=None,
        help="Optionally limit how many parameter sets to test for a fast profiling/smoke run",
    )
    parser.add_argument(
        "--feature-filters",
        nargs="*",
        default=None,
        metavar="FEATURE:VALUE",
        help=(
            "Post-filter signal rows before summary/ranking. Numeric values keep rows where "
            "feature >= value; ranges keep rows inside feature:low..high; comparison operators "
            "support feature<=value, feature>=value, feature<value, and feature>value; "
            "True/False values require boolean equality; other values require case-insensitive "
            "string equality. Example: --feature-filters gap_day_close_location_pct:48.6..54.7 "
            "gap_vol_ratio<=4.9 mb_quality:HIGH"
        ),
    )
    return parser


def limit_parameter_grid(
    grid: List[Dict[str, object]],
    max_param_sets: int | None,
) -> List[Dict[str, object]]:
    """Optionally cap the number of parameter sets for faster iteration."""
    if max_param_sets is None or max_param_sets <= 0:
        return grid
    return grid[:max_param_sets]


def apply_feature_filters(
    signals_df: pd.DataFrame,
    feature_filters: List[str] | None,
) -> pd.DataFrame:
    """Return signal rows that satisfy each feature filter specification."""
    if not feature_filters or signals_df.empty:
        return signals_df

    filtered = signals_df.copy()
    for spec in feature_filters:
        parsed = _parse_feature_filter_spec(spec)
        if parsed is None:
            continue
        feature, operator, raw_value = parsed
        if not feature or feature not in filtered.columns:
            continue

        if operator in {">", ">=", "<", "<="}:
            filtered = _apply_numeric_comparison_filter(
                filtered,
                feature,
                operator,
                raw_value,
            )
            continue

        if ".." in raw_value:
            filtered = _apply_numeric_range_filter(filtered, feature, raw_value)
            continue

        if raw_value.lower() in {"true", "false"}:
            expected = raw_value.lower() == "true"
            normalized = filtered[feature]
            if normalized.dtype != bool:
                normalized = normalized.astype(str).str.strip().str.lower().map(
                    {"true": True, "false": False}
                )
            filtered = filtered[normalized == expected]
            continue

        try:
            threshold = float(raw_value)
        except ValueError:
            filtered = filtered[
                filtered[feature].astype(str).str.strip().str.lower() == raw_value.lower()
            ]
            continue

        numeric = pd.to_numeric(filtered[feature], errors="coerce")
        filtered = filtered[numeric >= threshold]

    return filtered.reset_index(drop=True)


def _parse_feature_filter_spec(spec: str) -> tuple[str, str, str] | None:
    """Parse one feature-filter spec into feature, operator, and raw value."""
    stripped = spec.strip()
    for operator in ("<=", ">=", "<", ">"):
        if operator in stripped:
            feature, raw_value = stripped.split(operator, 1)
            return feature.strip(), operator, raw_value.strip()
    if ":" not in stripped:
        return None
    feature, raw_value = stripped.split(":", 1)
    return feature.strip(), ":", raw_value.strip()


def _apply_numeric_comparison_filter(
    signals_df: pd.DataFrame,
    feature: str,
    operator: str,
    raw_value: str,
) -> pd.DataFrame:
    """Apply one numeric comparison filter to signal rows."""
    try:
        threshold = float(raw_value)
    except ValueError:
        return signals_df

    numeric = pd.to_numeric(signals_df[feature], errors="coerce")
    if operator == "<=":
        return signals_df[numeric <= threshold]
    if operator == "<":
        return signals_df[numeric < threshold]
    if operator == ">=":
        return signals_df[numeric >= threshold]
    return signals_df[numeric > threshold]


def _apply_numeric_range_filter(
    signals_df: pd.DataFrame,
    feature: str,
    raw_value: str,
) -> pd.DataFrame:
    """Apply one inclusive numeric low..high range filter to signal rows."""
    low_raw, high_raw = raw_value.split("..", 1)
    try:
        low = float(low_raw)
        high = float(high_raw)
    except ValueError:
        return signals_df

    lower, upper = sorted((low, high))
    numeric = pd.to_numeric(signals_df[feature], errors="coerce")
    return signals_df[(numeric >= lower) & (numeric <= upper)]


def build_filtered_result_row(
    result: BacktestResult,
    filtered_signals: pd.DataFrame,
    feature_filters: List[str] | None,
) -> Dict[str, object]:
    """Return a calibration summary row whose metrics match the filtered signals."""
    row = result.to_dict()
    if not feature_filters:
        return row

    row["raw_n_signals"] = result.n_signals
    row["n_signals"] = len(filtered_signals)
    row["feature_filters"] = ";".join(feature_filters)
    summary_metrics = _compute_summary_metrics(
        filtered_signals,
        config.BACKTEST_SIGNAL_HORIZONS,
        config.BACKTEST_EXCURSION_HORIZONS,
    )
    row.update(summary_metrics)
    return row


def main() -> int:
    """Execute a calibration run for one scanner and persist a ranked report."""
    parser = build_parser()
    args = parser.parse_args()

    run_started_at = time.perf_counter()
    scanner_fn = get_scanner(args.scanner)
    full_grid = build_parameter_grid(args.scanner)
    grid = limit_parameter_grid(full_grid, args.max_param_sets)
    results = []
    signal_frames = []
    per_param_durations: List[float] = []

    data_load_started_at = time.perf_counter()
    symbols = get_universe_symbols(args.universe)
    end_with_horizon = (
        pd.Timestamp(args.end_date) + pd.tseries.offsets.BDay(max(config.BACKTEST_FORWARD_DAYS))
    ).date().isoformat()
    price_history = get_ohlcv_range(args.start_date, end_with_horizon, symbols=symbols)
    benchmark_history = get_ohlcv_range(
        args.start_date,
        end_with_horizon,
        symbols=config.BACKTEST_BENCHMARK_CANDIDATES,
    )
    breadth_history = get_breadth_range(args.start_date, args.end_date)
    prepared_history_by_date = prepare_scanner_history(
        scanner_fn,
        price_history,
        benchmark_history,
    )
    data_load_duration = time.perf_counter() - data_load_started_at

    print(
        f"Running calibration for {args.scanner} on {args.universe} "
        f"from {args.start_date} to {args.end_date} ({len(grid)} parameter sets)"
    )
    if args.max_param_sets is not None and len(grid) != len(full_grid):
        print(
            f"Fast-run mode: limited parameter grid from {len(full_grid)} to {len(grid)} sets"
        )
    print(
        f"Loaded {len(price_history):,} OHLCV rows for {len(symbols)} symbols through {end_with_horizon}"
    )
    print(f"Data load time: {_format_seconds(data_load_duration)}")

    for index, params in enumerate(grid, start=1):
        param_started_at = time.perf_counter()
        print(f"[{index}/{len(grid)}] Testing params: {params}")
        result = run_backtest(
            scanner_fn=scanner_fn,
            universe=args.universe,
            start_date=args.start_date,
            end_date=args.end_date,
            params=params,
            price_history=price_history,
            benchmark_history=benchmark_history,
            breadth_history=breadth_history,
            prepared_history_by_date=prepared_history_by_date,
        )
        param_duration = time.perf_counter() - param_started_at
        per_param_durations.append(param_duration)
        filtered_signals = apply_feature_filters(result.signal_results, args.feature_filters)
        results.append(build_filtered_result_row(result, filtered_signals, args.feature_filters))
        if not args.summary_only and not filtered_signals.empty:
            signal_frames.append(filtered_signals.copy())
        filtered_n = len(filtered_signals) if args.feature_filters else result.n_signals
        print(
            f"      Completed in {_format_seconds(param_duration)} "
            f"with {result.n_signals} raw signals"
            + (f" -> {filtered_n} after feature filters" if args.feature_filters else "")
        )

    if not results:
        print("No calibration results generated.")
        return 1

    ranking_started_at = time.perf_counter()
    result_df = rank_calibration_results(pd.DataFrame(results))
    ranking_duration = time.perf_counter() - ranking_started_at

    os.makedirs(config.BACKTEST_OUTPUT_DIR, exist_ok=True)
    output_path, signals_output_path = build_output_paths(
        date.today().isoformat(),
        args.scanner,
        args.universe,
        args.label,
    )

    summary_write_started_at = time.perf_counter()
    result_df.to_csv(output_path, index=False)
    summary_write_duration = time.perf_counter() - summary_write_started_at

    if signal_frames:
        signals_write_started_at = time.perf_counter()
        signals_df = pd.concat(signal_frames, ignore_index=True)
        signals_df.to_csv(signals_output_path, index=False)
        signals_write_duration = time.perf_counter() - signals_write_started_at
    else:
        signals_output_path = None
        signals_write_duration = 0.0

    total_duration = time.perf_counter() - run_started_at
    print(
        "Ranking parameter sets by median alpha 5d, then win rate 5d, "
        "then 5d target-hit rate, then average MAE 5d, then signal count."
    )
    print(result_df.head(10).to_string(index=False))
    print(f"\nSaved calibration summary to {output_path}")
    if signals_output_path is not None:
        print(f"Saved signal-level report to {signals_output_path}")
    elif args.summary_only:
        print("Signal-level CSV skipped due to --summary-only")
    if per_param_durations:
        print(
            "Timing summary: "
            f"data_load={_format_seconds(data_load_duration)}, "
            f"avg_param={_format_seconds(sum(per_param_durations) / len(per_param_durations))}, "
            f"ranking={_format_seconds(ranking_duration)}, "
            f"summary_write={_format_seconds(summary_write_duration)}, "
            f"signals_write={_format_seconds(signals_write_duration)}, "
            f"total={_format_seconds(total_duration)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
