#!/usr/bin/env python3
"""Run scanner parameter calibration against stored OHLCV history."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.store import get_ohlcv_range
from src.ingestion.symbols import get_universe_symbols
from src.review.backtest import build_parameter_grid, get_scanner, run_backtest


def main() -> int:
    """Execute a calibration run for one scanner and persist a ranked report."""
    parser = argparse.ArgumentParser(description="Calibrate scanner thresholds")
    parser.add_argument("--scanner", default="momentum_burst")
    parser.add_argument("--universe", default=config.UNIVERSE)
    parser.add_argument(
        "--start-date",
        default=(pd.Timestamp.today() - pd.DateOffset(years=config.BACKTEST_YEARS)).date().isoformat(),
    )
    parser.add_argument("--end-date", default=pd.Timestamp.today().date().isoformat())
    args = parser.parse_args()

    scanner_fn = get_scanner(args.scanner)
    grid = build_parameter_grid(args.scanner)
    results = []
    symbols = get_universe_symbols(args.universe)
    end_with_horizon = (
        pd.Timestamp(args.end_date) + pd.tseries.offsets.BDay(max(config.BACKTEST_FORWARD_DAYS))
    ).date().isoformat()
    price_history = get_ohlcv_range(args.start_date, end_with_horizon, symbols=symbols)

    print(
        f"Running calibration for {args.scanner} on {args.universe} "
        f"from {args.start_date} to {args.end_date} ({len(grid)} parameter sets)"
    )
    print(
        f"Loaded {len(price_history):,} OHLCV rows for {len(symbols)} symbols through {end_with_horizon}"
    )
    for index, params in enumerate(grid, start=1):
        print(f"[{index}/{len(grid)}] Testing params: {params}")
        result = run_backtest(
            scanner_fn=scanner_fn,
            universe=args.universe,
            start_date=args.start_date,
            end_date=args.end_date,
            params=params,
            price_history=price_history,
        )
        results.append(result.to_dict())

    if not results:
        print("No calibration results generated.")
        return 1

    result_df = pd.DataFrame(results).sort_values(
        ["win_rate_10d", "avg_return_10d", "n_signals"],
        ascending=[False, False, False],
    )
    os.makedirs(config.BACKTEST_OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(
        config.BACKTEST_OUTPUT_DIR,
        f"{date.today().isoformat()}-{args.scanner}-{args.universe}.csv",
    )
    result_df.to_csv(output_path, index=False)
    print(result_df.head(10).to_string(index=False))
    print(f"\nSaved calibration report to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
