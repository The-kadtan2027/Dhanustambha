"""Business operations for manual trade logging and status reporting."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

import config
from src.ingestion.store import (
    get_breadth,
    get_latest_close,
    get_trade,
    get_trades,
    save_trade,
    update_trade,
)
from src.trade.pnl import compute_expectancy, compute_r_multiple, compute_trade_pnl


logger = logging.getLogger(__name__)


def get_market_verdict(as_of_date: Optional[str] = None) -> str:
    """Return the latest known market verdict, defaulting to OFFENSIVE."""
    breadth = get_breadth(as_of_date)
    verdict = str(breadth.get("verdict", "")).upper()
    if verdict in {"OFFENSIVE", "DEFENSIVE", "AVOID"}:
        return verdict

    logger.warning("No breadth verdict found for %s; defaulting to OFFENSIVE", as_of_date or "latest")
    return "OFFENSIVE"


def get_open_trades() -> pd.DataFrame:
    """Return currently open trades."""
    return get_trades(status=config.TRADE_DEFAULT_STATUS_OPEN)


def get_closed_trades(last_n_days: int = 90) -> pd.DataFrame:
    """Return closed trades, optionally restricted by recent exit date."""
    closed_statuses = {
        config.TRADE_STATUS_CLOSED_WIN,
        config.TRADE_STATUS_CLOSED_LOSS,
        config.TRADE_STATUS_CLOSED_BE,
    }
    trades = get_trades()
    if trades.empty:
        return trades

    closed = trades[trades["status"].isin(closed_statuses)].copy()
    if closed.empty:
        return closed

    closed["exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce")
    if last_n_days > 0:
        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=last_n_days)
        closed = closed[closed["exit_date"] >= cutoff]
    return closed.sort_values("exit_date", ascending=False).reset_index(drop=True)


def open_trade(
    symbol: str,
    setup_type: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    stop_price: float,
    target_price: Optional[float] = None,
    notes: str = "",
    grade: str = "",
) -> int:
    """Persist a new manual trade after validating portfolio-level constraints."""
    open_trades = get_open_trades()
    if len(open_trades) >= config.TRADE_MAX_OPEN:
        raise ValueError(
            f"Cannot open more than {config.TRADE_MAX_OPEN} concurrent trades."
        )

    if shares <= 0:
        raise ValueError("Shares must be positive.")

    record = {
        "symbol": symbol.strip().upper(),
        "setup_type": setup_type.strip().upper(),
        "entry_date": entry_date,
        "entry_price": float(entry_price),
        "shares": int(shares),
        "stop_price": float(stop_price),
        "target_price": float(target_price) if target_price is not None else None,
        "notes": notes.strip(),
        "status": config.TRADE_DEFAULT_STATUS_OPEN,
        "grade": grade.strip().upper() if grade else None,
    }
    return save_trade(record)


def close_trade(
    trade_id: int,
    exit_date: str,
    exit_price: float,
    notes: str = "",
) -> Dict[str, object]:
    """Close an open trade and return the computed closure details."""
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} does not exist.")

    if trade.get("status") != config.TRADE_DEFAULT_STATUS_OPEN:
        raise ValueError(f"Trade {trade_id} is not open.")

    pnl = compute_trade_pnl(
        float(trade["entry_price"]),
        float(exit_price),
        int(trade["shares"]),
    )
    r_multiple = compute_r_multiple(
        float(trade["entry_price"]),
        float(exit_price),
        float(trade["stop_price"]),
    )

    if pnl > 0:
        status = config.TRADE_STATUS_CLOSED_WIN
    elif pnl < 0:
        status = config.TRADE_STATUS_CLOSED_LOSS
    else:
        status = config.TRADE_STATUS_CLOSED_BE

    update_trade(
        trade_id,
        {
            "exit_date": exit_date,
            "exit_price": float(exit_price),
            "pnl": round(float(pnl), 2),
            "status": status,
            "notes": notes.strip() or trade.get("notes"),
        },
    )

    return {
        "trade_id": trade_id,
        "symbol": trade["symbol"],
        "status": status,
        "pnl": round(float(pnl), 2),
        "r_multiple": round(float(r_multiple), 2),
    }


def build_open_trade_status(as_of_date: Optional[str] = None) -> pd.DataFrame:
    """Return open trades augmented with latest-close unrealized P&L when available."""
    open_trades = get_open_trades()
    if open_trades.empty:
        return open_trades

    status_df = open_trades.copy()
    current_prices = []
    unrealized_pnls = []

    for _, row in status_df.iterrows():
        latest_close = get_latest_close(str(row["symbol"]), up_to_date=as_of_date)
        current_prices.append(latest_close)
        if latest_close is None:
            unrealized_pnls.append(None)
        else:
            unrealized_pnls.append(
                round(
                    compute_trade_pnl(
                        float(row["entry_price"]),
                        float(latest_close),
                        int(row["shares"]),
                    ),
                    2,
                )
            )

    status_df["current_close"] = current_prices
    status_df["unrealized_pnl"] = unrealized_pnls
    return status_df


def summarize_closed_trades(last_n_days: int = 90) -> Dict[str, float]:
    """Summarize closed trades using expectancy-style metrics."""
    closed = get_closed_trades(last_n_days=last_n_days)
    return compute_expectancy(closed)
