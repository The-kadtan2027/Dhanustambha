"""Business operations for manual trade logging and status reporting."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import pandas as pd

import config
from src.ingestion.store import (
    get_breadth,
    get_latest_close,
    get_stored_dates,
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

    logger.warning(
        "No breadth verdict found for %s; defaulting to OFFENSIVE",
        as_of_date or "latest",
    )
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

    if entry_price <= 0:
        raise ValueError("Entry price must be positive.")

    if stop_price <= 0:
        raise ValueError("Stop price must be positive.")

    if stop_price >= entry_price:
        raise ValueError("Stop price must be below entry price.")

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


def update_stop_price(trade_id: int, stop_price: float) -> Dict[str, object]:
    """Update the stop price for an open trade and return the updated details."""
    trade = get_trade(trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} does not exist.")

    if trade.get("status") != config.TRADE_DEFAULT_STATUS_OPEN:
        raise ValueError(f"Trade {trade_id} is not open.")

    if stop_price <= 0:
        raise ValueError("Stop price must be positive.")

    update_trade(trade_id, {"stop_price": float(stop_price)})
    return {
        "trade_id": trade_id,
        "symbol": trade["symbol"],
        "old_stop_price": float(trade["stop_price"]),
        "new_stop_price": float(stop_price),
    }


def count_trading_days_held(entry_date: str, as_of_date: Optional[str] = None) -> int:
    """Count stored NSE trading dates after entry date through the as-of date."""
    stored_dates = get_stored_dates(start_date=entry_date, end_date=as_of_date)
    return len([stored_date for stored_date in stored_dates if stored_date > entry_date])


def determine_action_required(
    entry_price: float,
    stop_price: float,
    pct_gain: Optional[float],
    days_held: int,
    current_price: Optional[float] = None,
) -> str:
    """Return the trade-management action required by current gain and holding age."""
    if current_price is not None and current_price <= stop_price:
        return "STOP_LOSS_HIT"

    if days_held >= config.TRADE_TIME_EXIT_DAYS:
        return "TIME_EXIT"

    if pct_gain is not None:
        if pct_gain >= config.TRADE_TRAIL_TIER_3_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_3_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_7_5PCT"
                
        if pct_gain >= config.TRADE_TRAIL_TIER_2_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_2_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_3PCT"
                
        if pct_gain >= config.TRADE_TRAIL_TIER_1_TRIGGER_PCT:
            expected_stop = entry_price * (1 + (config.TRADE_TRAIL_TIER_1_STOP_PCT / 100))
            if stop_price < expected_stop:
                return "TRAIL_TO_BREAKEVEN"

    return "NONE"


def build_open_trade_status(
    as_of_date: Optional[str] = None, current_prices: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """Return open trades augmented with price, P&L, holding age, and action flags.

    If current_prices is provided, it is used instead of the latest stored EOD close.
    """
    open_trades = get_open_trades()
    if open_trades.empty:
        return open_trades

    status_df = open_trades.copy()
    current_prices_list = []
    unrealized_pnls = []
    pct_gains = []
    days_held_values = []
    actions_required = []

    for _, row in status_df.iterrows():
        symbol = str(row["symbol"])
        if current_prices and symbol in current_prices:
            latest_close = current_prices[symbol]
        else:
            latest_close = get_latest_close(symbol, up_to_date=as_of_date)
        
        current_prices_list.append(latest_close)
        if latest_close is None:
            unrealized_pnls.append(None)
            pct_gain = None
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
            pct_gain = round(
                (
                    (float(latest_close) - float(row["entry_price"]))
                    / float(row["entry_price"])
                )
                * 100,
                2,
            )

        days_held = count_trading_days_held(str(row["entry_date"]), as_of_date=as_of_date)
        pct_gains.append(pct_gain)
        days_held_values.append(days_held)
        actions_required.append(
            determine_action_required(
                entry_price=float(row["entry_price"]),
                stop_price=float(row["stop_price"]),
                pct_gain=pct_gain,
                days_held=days_held,
                current_price=float(latest_close) if latest_close is not None else None,
            )
        )

    status_df["current_close"] = current_prices_list
    status_df["unrealized_pnl"] = unrealized_pnls
    status_df["pct_gain"] = pct_gains
    status_df["days_held"] = days_held_values
    status_df["action_required"] = actions_required
    return status_df


def summarize_closed_trades(last_n_days: int = 90) -> Dict[str, float]:
    """Summarize closed trades using expectancy-style metrics."""
    closed = get_closed_trades(last_n_days=last_n_days)
    return compute_expectancy(closed)


def build_portfolio_summary(current_prices: Optional[Dict[str, float]] = None) -> dict:
    """Return portfolio-level aggregates for all open trades."""
    trades = build_open_trade_status(current_prices=current_prices)
    if trades.empty:
        return {
            "trade_count": 0,
            "total_invested": 0.0,
            "total_pnl": 0.0,
            "open_risk": 0.0,
            "locked_profit": 0.0,
        }

    total_invested = float((trades["entry_price"] * trades["shares"]).sum())
    total_pnl = float(trades["unrealized_pnl"].fillna(0).sum())
    # open_risk = sum of money at risk if stop is hit
    open_risk = float(((trades["entry_price"] - trades["stop_price"]) * trades["shares"]).sum())
    # locked_profit = money protected when stop > entry (trailing to profit)
    trades["stop_above_entry"] = (trades["stop_price"] > trades["entry_price"]).astype(float)
    locked_profit = float(
        ((trades["stop_price"] - trades["entry_price"]) * trades["shares"] * trades["stop_above_entry"]).sum()
    )
    return {
        "trade_count": int(len(trades)),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "open_risk": round(open_risk, 2),
        "locked_profit": round(locked_profit, 2),
    }
