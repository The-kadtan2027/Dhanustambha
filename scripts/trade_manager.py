#!/usr/bin/env python3
"""Interactive CLI for manual trade management in Phase 2."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from typing import Optional

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from src.ingestion.store import init_db
from src.trade.log import (
    build_open_trade_status,
    close_trade,
    get_market_verdict,
    get_open_trades,
    open_trade,
    summarize_closed_trades,
)
from src.trade.sizer import calculate_position_size


def prompt_text(message: str, default: str = "") -> str:
    """Prompt for free text with an optional default."""
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or default


def prompt_float(
    message: str,
    default: Optional[float] = None,
    allow_blank: bool = False,
) -> Optional[float]:
    """Prompt until a valid floating-point value is entered."""
    while True:
        raw = prompt_text(message, "" if default is None else str(default))
        if allow_blank and raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            print("Please enter a valid number.")


def prompt_int(message: str, default: Optional[int] = None) -> int:
    """Prompt until a valid integer value is entered."""
    while True:
        raw = prompt_text(message, "" if default is None else str(default))
        try:
            return int(raw)
        except ValueError:
            print("Please enter a valid integer.")


def confirm(message: str) -> bool:
    """Prompt for yes/no confirmation."""
    return prompt_text(f"{message} [y/N]").lower() == "y"


def format_table(df: pd.DataFrame) -> str:
    """Render a DataFrame for terminal output."""
    if df.empty:
        return "(none)"
    return df.to_string(index=False)


def handle_open() -> int:
    """Open a new manual trade."""
    symbol = prompt_text("Symbol").upper()
    setup_type = prompt_text("Setup type", "MOMENTUM_BURST").upper()
    entry_date = prompt_text("Entry date", date.today().isoformat())
    entry_price = prompt_float("Entry price")
    stop_price = prompt_float("Stop price")
    target_price = prompt_float("Target price", allow_blank=True)
    notes = prompt_text("Notes", "")
    grade = prompt_text("Grade (A/B/C)", "")

    market_verdict = get_market_verdict(entry_date)
    sizing = calculate_position_size(
        account_size=config.ACCOUNT_SIZE,
        entry_price=float(entry_price),
        stop_price=float(stop_price),
        market_verdict=market_verdict,
    )
    if sizing is None:
        print("Trade rejected: invalid sizing inputs.")
        return 1

    print("\nProposed trade")
    print(f"  Market verdict:  {market_verdict}")
    print(f"  Shares:          {int(sizing['shares'])}")
    print(f"  Position value:  INR {sizing['position_value']:.2f}")
    print(f"  Risk amount:     INR {sizing['risk_amount']:.2f}")
    print(f"  R unit:          INR {sizing['r_unit']:.2f}")

    if not confirm("Save this trade?"):
        print("Trade discarded.")
        return 0

    trade_id = open_trade(
        symbol=symbol,
        setup_type=setup_type,
        entry_date=entry_date,
        entry_price=float(entry_price),
        shares=int(sizing["shares"]),
        stop_price=float(stop_price),
        target_price=target_price,
        notes=notes,
        grade=grade,
    )
    print(f"Trade saved with ID {trade_id}.")
    return 0


def handle_close() -> int:
    """Close an existing trade."""
    open_positions = get_open_trades()
    if open_positions.empty:
        print("No open trades to close.")
        return 0

    print(format_table(open_positions[["id", "symbol", "setup_type", "entry_date", "entry_price", "shares"]]))
    trade_id = prompt_int("Trade ID to close")
    exit_date = prompt_text("Exit date", date.today().isoformat())
    exit_price = prompt_float("Exit price")
    notes = prompt_text("Close notes", "")

    result = close_trade(
        trade_id=trade_id,
        exit_date=exit_date,
        exit_price=float(exit_price),
        notes=notes,
    )
    print("\nTrade closed")
    print(f"  Symbol:      {result['symbol']}")
    print(f"  Status:      {result['status']}")
    print(f"  P&L:         INR {result['pnl']:.2f}")
    print(f"  R multiple:  {result['r_multiple']:.2f}R")
    return 0


def handle_status() -> int:
    """Show open trade status."""
    status_df = build_open_trade_status()
    if status_df.empty:
        print("No open trades.")
        return 0

    columns = [
        "id",
        "symbol",
        "setup_type",
        "entry_date",
        "entry_price",
        "shares",
        "stop_price",
        "current_close",
        "unrealized_pnl",
    ]
    print(format_table(status_df[columns]))
    return 0


def handle_summary() -> int:
    """Show closed-trade summary statistics."""
    summary = summarize_closed_trades()
    print("Closed trade summary")
    print(f"  Total trades:   {int(summary['total_trades'])}")
    print(f"  Win rate:       {summary['win_rate']:.1f}%")
    print(f"  Avg win:        {summary['avg_win_r']:.2f}R")
    print(f"  Avg loss:       {summary['avg_loss_r']:.2f}R")
    print(f"  Expectancy:     {summary['expectancy_r']:.2f}R")
    return 0


def main() -> int:
    """Parse CLI arguments and dispatch to the requested command."""
    init_db()

    parser = argparse.ArgumentParser(description="Dhanustambha trade manager")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("open", help="Open a new manual trade")
    subparsers.add_parser("close", help="Close an existing trade")
    subparsers.add_parser("status", help="Show open trade status")
    subparsers.add_parser("summary", help="Show closed trade summary")

    args = parser.parse_args()
    if args.command == "open":
        return handle_open()
    if args.command == "close":
        return handle_close()
    if args.command == "status":
        return handle_status()
    if args.command == "summary":
        return handle_summary()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
