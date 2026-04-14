#!/usr/bin/env python3
"""Backfill multiple years of daily OHLCV history for a configured universe."""

from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.fetcher import fetch_historical_data
from src.ingestion.store import get_ohlcv_range, init_db, upsert_ohlcv
from src.ingestion.symbols import get_universe_symbols


def main() -> int:
    """Run a historical backfill for the selected universe."""
    parser = argparse.ArgumentParser(description="Backfill historical OHLCV data")
    parser.add_argument("--years", type=int, default=config.BACKTEST_YEARS)
    parser.add_argument("--universe", default=config.UNIVERSE)
    parser.add_argument("--end-date", default=pd.Timestamp.today().date().isoformat())
    args = parser.parse_args()

    init_db()

    end_date = pd.Timestamp(args.end_date)
    start_date = (end_date - pd.DateOffset(years=args.years)).date().isoformat()
    end_date_str = end_date.date().isoformat()
    symbols = get_universe_symbols(args.universe)

    existing = get_ohlcv_range(start_date, end_date_str, symbols=symbols)
    existing_counts = existing.groupby("symbol").size().to_dict() if not existing.empty else {}
    target_symbols = [symbol for symbol in symbols if existing_counts.get(symbol, 0) < 600]

    print(f"Universe: {args.universe}")
    print(f"Date range: {start_date} -> {end_date_str}")
    print(f"Symbols requiring backfill: {len(target_symbols)} / {len(symbols)}")

    if not target_symbols:
        print("Historical data already present for all symbols.")
        return 0

    rows = fetch_historical_data(target_symbols, start_date, end_date_str)
    if not rows:
        print("No historical rows fetched.")
        return 1

    written = upsert_ohlcv(rows)
    print(f"Stored {written} OHLCV rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
