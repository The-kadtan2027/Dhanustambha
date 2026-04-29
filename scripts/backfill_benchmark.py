#!/usr/bin/env python3
"""Backfill benchmark OHLCV history for alpha-aware calibration runs."""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.fetcher import fetch_benchmark_history
from src.ingestion.store import get_ohlcv_range, init_db, upsert_ohlcv


def main() -> int:
    """Backfill a benchmark series like ^NSEI into the shared OHLCV table."""
    parser = argparse.ArgumentParser(description="Backfill benchmark OHLCV history")
    parser.add_argument("--years", type=int, default=config.BACKTEST_YEARS)
    parser.add_argument("--symbol", default=config.BACKTEST_BENCHMARK_SYMBOL)
    parser.add_argument(
        "--source-ticker",
        default=None,
        help="Optional yfinance ticker override if it differs from the stored symbol",
    )
    parser.add_argument("--end-date", default=pd.Timestamp.today().date().isoformat())
    args = parser.parse_args()

    init_db()

    end_date = pd.Timestamp(args.end_date)
    start_date = (end_date - pd.DateOffset(years=args.years)).date().isoformat()
    end_date_str = end_date.date().isoformat()

    existing = get_ohlcv_range(start_date, end_date_str, symbols=[args.symbol])
    existing_count = len(existing)

    print(f"Benchmark symbol: {args.symbol}")
    print(f"Source ticker: {args.source_ticker or args.symbol}")
    print(f"Date range: {start_date} -> {end_date_str}")
    print(f"Existing rows in range: {existing_count}")

    rows = fetch_benchmark_history(
        benchmark_symbol=args.symbol,
        start_date=start_date,
        end_date=end_date_str,
        source_ticker=args.source_ticker,
    )
    if not rows:
        print("No benchmark rows fetched.")
        return 1

    written = upsert_ohlcv(rows)
    print(f"Stored {written} benchmark OHLCV rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
