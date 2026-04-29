#!/usr/bin/env python3
"""Backfill historical breadth rows from stored OHLCV data."""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.store import get_ohlcv_range, init_db, save_breadth
from src.ingestion.symbols import get_universe_symbols
from src.monitor.breadth import compute_historical_breadth
from src.monitor.verdict import compute_verdict


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for breadth backfill runs."""
    parser = argparse.ArgumentParser(description="Backfill historical breadth rows")
    parser.add_argument("--universe", default=config.UNIVERSE)
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date to persist breadth rows for (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date to persist breadth rows for (YYYY-MM-DD)",
    )
    return parser


def main() -> int:
    """Compute and persist breadth history for the requested window."""
    parser = build_parser()
    args = parser.parse_args()

    start_timestamp = pd.Timestamp(args.start_date)
    end_timestamp = pd.Timestamp(args.end_date)
    warmup_start = (start_timestamp - pd.tseries.offsets.BDay(252)).date().isoformat()

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    init_db()

    symbols = get_universe_symbols(args.universe)
    print(
        f"Loading OHLCV history for {len(symbols)} symbols from {warmup_start} to {args.end_date}..."
    )
    history = get_ohlcv_range(warmup_start, args.end_date, symbols=symbols)
    if history.empty:
        print("No OHLCV history found for the requested range.")
        return 1

    print("Computing historical breadth metrics...")
    breadth_df = compute_historical_breadth(history)
    if breadth_df.empty:
        print("No breadth rows could be computed from the available OHLCV history.")
        return 1

    breadth_df = breadth_df[
        (breadth_df["date"] >= start_timestamp) & (breadth_df["date"] <= end_timestamp)
    ].copy()
    if breadth_df.empty:
        print("No eligible breadth rows fall inside the requested window.")
        return 1

    breadth_df["verdict"] = breadth_df.apply(
        lambda row: compute_verdict(row.to_dict()),
        axis=1,
    )

    print(f"Saving {len(breadth_df)} breadth rows...")
    for record in breadth_df.to_dict(orient="records"):
        record["date"] = pd.Timestamp(record["date"]).date().isoformat()
        save_breadth(record)

    print(
        f"Saved breadth history for {len(breadth_df)} trading days "
        f"from {args.start_date} to {args.end_date}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
