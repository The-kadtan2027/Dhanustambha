#!/usr/bin/env python3
"""Dhanustambha daily briefing entrypoint for the Phase 1 MVP."""

import argparse
import logging
import os
import sys
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.fetcher import fetch_eod_data_for_dates, get_business_day_range
from src.ingestion.store import (
    get_all_symbols_ohlcv,
    get_stored_dates,
    init_db,
    save_breadth,
    upsert_ohlcv,
)
from src.ingestion.symbols import get_universe_symbols
from src.monitor.breadth import compute_breadth
from src.monitor.verdict import compute_verdict
from src.scanner.episodic_pivot import detect_episodic_pivot
from src.scanner.momentum_burst import detect_momentum_burst
from src.scanner.trend_intensity import detect_trend_intensity
from src.scanner.watchlist import export_watchlist, merge_and_rank


os.makedirs(config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(config.LOG_DIR, "briefing.log")),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def is_eod_data_expected(
    fetch_date: str, current_time: Optional[datetime] = None
) -> bool:
    """Return whether NSE EOD data should be available for the requested date."""
    if current_time is None:
        current_time = datetime.now(IST)
    elif current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=IST)
    else:
        current_time = current_time.astimezone(IST)

    target_date = pd.Timestamp(fetch_date).date()
    if target_date < current_time.date():
        return True
    if target_date > current_time.date():
        return False

    pull_hour, pull_minute = [int(part) for part in config.DATA_PULL_TIME.split(":", maxsplit=1)]
    pull_time = datetime.combine(
        target_date,
        time(hour=pull_hour, minute=pull_minute),
        tzinfo=IST,
    )
    availability_time = pull_time + pd.Timedelta(minutes=config.DATA_PULL_GRACE_MINUTES)
    return current_time >= availability_time


def _print_setup_table(title: str, candidates: pd.DataFrame) -> None:
    """Print one setup-specific candidate section with quality/tier labels."""
    print(f"\n  {'-' * 45}")
    print(f"  {title} ({len(candidates)})")
    print(f"  {'-' * 45}")

    if candidates.empty:
        print("  No candidates.")
        return

    # Determine the tier/quality column and sort high-quality first
    tier_col = None
    high_values = set()
    if "ep_tier" in candidates.columns:
        tier_col = "ep_tier"
        high_values = {"A+"}
    elif "mb_quality" in candidates.columns:
        tier_col = "mb_quality"
        high_values = {"HIGH"}

    if tier_col:
        candidates = candidates.copy()
        candidates["_tier_sort"] = candidates[tier_col].apply(
            lambda v: 0 if v in high_values else 1
        )
        candidates = candidates.sort_values(
            ["_tier_sort", "score"], ascending=[True, False]
        )

    print(
        f"  {'':3s}{'SYMBOL':<12} {'MATCHED_SETUPS':<28} "
        f"{'%CHG':>6} {'VOL_RATIO':>10} {'PRICE':>8} {'STOP_LOSS':^14}"
    )
    print(f"  {'-' * 88}")
    for _, row in candidates.iterrows():
        matched_setups = row.get("matched_setups", row.get("setup_type", ""))
        tier_label = ""
        if tier_col and row.get(tier_col) in high_values:
            tier_label = "* "
            
        # Add Stop Loss recommendations
        stop_pct = 2.5 # default fallback
        if "EPISODIC" in str(matched_setups).upper():
            stop_pct = config.TRADE_EP_STOP_PCT
        elif "MOMENTUM" in str(matched_setups).upper():
            stop_pct = config.TRADE_MB_STOP_PCT
        elif "TREND" in str(matched_setups).upper():
            stop_pct = config.TRADE_TI_STOP_PCT
            
        stop_val = max(0, row['close'] * (1 - (stop_pct / 100)))

        print(
            f"  {tier_label:3s}{row['symbol']:<12} {matched_setups:<28} "
            f"{row['pct_change']:>+6.1f}% {row['volume_ratio']:>9.1f}x "
            f"{row['close']:>8.2f} {stop_val:>8.2f} ({stop_pct:3.1f}%)"
        )


def run_briefing(fetch_date: Optional[str] = None, history_days: Optional[int] = None) -> None:
    """Run the full end-of-day briefing workflow for one trading date."""
    if fetch_date is None:
        fetch_date = date.today().isoformat()
    if history_days is None:
        history_days = config.BRIEFING_HISTORY_DAYS

    print(f"\n{'=' * 55}")
    print(f"  Dhanustambha Daily Briefing - {fetch_date}")
    print(f"{'=' * 55}")

    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
    os.makedirs(config.WATCHLIST_DIR, exist_ok=True)
    init_db()

    symbols = get_universe_symbols(config.UNIVERSE)
    start_date = (
        pd.Timestamp(fetch_date) - pd.tseries.offsets.BDay(history_days)
    ).date().isoformat()
    requested_dates = get_business_day_range(start_date, fetch_date)
    stored_dates = set(get_stored_dates(start_date, fetch_date))
    missing_dates = [current_date for current_date in requested_dates if current_date not in stored_dates]
    target_date_expected = is_eod_data_expected(fetch_date)
    fetch_dates = missing_dates
    if not target_date_expected:
        fetch_dates = [current_date for current_date in missing_dates if current_date < fetch_date]

    print(f"\n[1/4] Ensuring OHLCV history for {len(symbols)} symbols...")
    print(
        f"      Need {len(requested_dates)} trading days of history; "
        f"{len(missing_dates)} trading days missing from the DB"
    )

    rows = fetch_eod_data_for_dates(symbols, fetch_dates)
    if rows:
        upsert_ohlcv(rows)
        print(f"      OK {len(rows)} OHLCV rows fetched and stored")
    elif not missing_dates:
        print("      OK Required history already present in the DB")

    target_in_db = fetch_date in set(get_stored_dates(fetch_date, fetch_date))
    if target_in_db and missing_dates and not rows:
        print(
            f"      OK Missing dates were NSE holidays; "
            f"target date {fetch_date} data already present in DB"
        )
    elif not target_in_db:
        if not target_date_expected:
            print(
                f"      Waiting for NSE EOD data for {fetch_date}; "
                f"rerun after {config.DATA_PULL_TIME} IST + "
                f"{config.DATA_PULL_GRACE_MINUTES}m grace"
            )
            return
        if missing_dates:
            print(
                "      X No data fetched and target date not in DB — "
                "is today a market holiday?"
            )
            return


    print("\n[2/4] Computing Market Monitor breadth...")
    all_data = get_all_symbols_ohlcv(fetch_date)
    metrics = compute_breadth(all_data)
    verdict = compute_verdict(metrics)
    if metrics:
        metrics["verdict"] = verdict
        save_breadth(metrics)

    verdict_icon = {
        "OFFENSIVE": "[OK]",
        "DEFENSIVE": "[!]",
        "AVOID": "[X]",
    }.get(verdict, "[?]")

    print(f"\n  {'-' * 45}")
    print("  MARKET MONITOR")
    print(f"  {'-' * 45}")
    print(f"  Stocks above MA20:    {metrics.get('pct_above_ma20', 0):.1f}%")
    print(f"  Stocks above MA50:    {metrics.get('pct_above_ma50', 0):.1f}%")
    print(f"  New 52w highs:        {metrics.get('new_highs_52w', 0)}")
    print(f"  New 52w lows:         {metrics.get('new_lows_52w', 0)}")
    print(f"  Up-volume ratio:      {metrics.get('up_volume_ratio', 0):.2f}")
    print(f"  Advancing / Declining:{metrics.get('advancing', 0)} / {metrics.get('declining', 0)}")
    print(f"  Verdict:              {verdict} {verdict_icon}")

    if verdict == "AVOID":
        print("\n  [X] AVOID - No new trades. Protect capital.")
        print(f"{'=' * 55}\n")
        return

    print(f"\n[3/4] Running setup scanners (market is {verdict})...")
    mb_results = detect_momentum_burst(all_data)
    ep_results = detect_episodic_pivot(all_data)
    ti_results = detect_trend_intensity(all_data)
    print(f"      Momentum Burst:    {len(mb_results)} candidates")
    print(f"      Episodic Pivot:    {len(ep_results)} candidates")
    print(f"      Trend Intensity:   {len(ti_results)} candidates")

    print("\n[4/4] Building watchlist...")
    watchlist = merge_and_rank([mb_results, ep_results, ti_results], fetch_date)
    if watchlist.empty:
        print("      No candidates today.")
        print(f"{'=' * 55}\n")
        return

    csv_path = export_watchlist(watchlist, fetch_date)

    print(f"\n  {'-' * 45}")
    print(f"  TOP CANDIDATES ({len(watchlist)})")
    print(f"  {'-' * 45}")
    print(
        f"  {'':3s}{'SYMBOL':<12} {'SETUP':<14} {'MATCHED_SETUPS':<22} "
        f"{'%CHG':>6} {'VOL_RATIO':>10} {'PRICE':>8} {'STOP_LOSS':^14}"
    )
    print(f"  {'-' * 105}")
    for _, row in watchlist.iterrows():
        matched_setups = row.get("matched_setups", row["setup_type"])
        # Show quality/tier marker for high-conviction candidates
        tier_label = ""
        if row.get("ep_tier") == "A+":
            tier_label = "* "
        elif row.get("mb_quality") == "HIGH":
            tier_label = "* "
            
        # Add Stop Loss recommendations
        stop_pct = 2.5 # default fallback
        if "EPISODIC" in str(matched_setups).upper() or "EP_TIER" in row:
            stop_pct = config.TRADE_EP_STOP_PCT
        elif "MOMENTUM" in str(matched_setups).upper() or "MB_QUALITY" in row:
            stop_pct = config.TRADE_MB_STOP_PCT
        elif "TREND" in str(matched_setups).upper():
            stop_pct = config.TRADE_TI_STOP_PCT
            
        stop_val = max(0, row['close'] * (1 - (stop_pct / 100)))

        print(
            f"  {tier_label:3s}{row['symbol']:<12} {row['setup_type']:<14} "
            f"{matched_setups:<22} "
            f"{row['pct_change']:>+6.1f}% {row['volume_ratio']:>9.1f}x "
            f"{row['close']:>8.2f} {stop_val:>8.2f} ({stop_pct:3.1f}%)"
        )

    _print_setup_table("TOP MOMENTUM BURST", mb_results)
    _print_setup_table("TOP EPISODIC PIVOT", ep_results)
    _print_setup_table("TOP TREND INTENSITY", ti_results)

    print(f"\n  Watchlist saved -> {csv_path}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dhanustambha Daily Briefing")
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
    parser.add_argument(
        "--history-days",
        type=int,
        default=config.BRIEFING_HISTORY_DAYS,
        help="Business-day lookback to ensure before running the briefing",
    )
    args = parser.parse_args()
    run_briefing(fetch_date=args.date, history_days=args.history_days)
