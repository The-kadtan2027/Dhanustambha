"""Trade performance calculation module (P&L, R-multiples, Expectancy)."""

from typing import Dict
import pandas as pd


def compute_trade_pnl(entry_price: float, exit_price: float, shares: int) -> float:
    """Compute raw P&L amount."""
    # Assuming long trades for momentum strategies
    return (exit_price - entry_price) * shares


def compute_r_multiple(entry_price: float, exit_price: float, stop_price: float) -> float:
    """Compute R-multiple (reward relative to initial risk).

    Example: Risking ₹5 (entry 100, stop 95). If exit at 115 (+₹15), R = +3R.
    """
    initial_risk = entry_price - stop_price
    if initial_risk <= 0:
        return 0.0

    return (exit_price - entry_price) / initial_risk


def compute_expectancy(closed_trades_df: pd.DataFrame) -> Dict[str, float]:
    """Compute overall expectancy metrics from a closed trades dataframe.

    The DataFrame should have at least the columns: 'entry_price', 'exit_price', 'stop_price'.
    """
    if closed_trades_df.empty:
        return {
            "win_rate": 0.0,
            "avg_win_r": 0.0,
            "avg_loss_r": 0.0,
            "expectancy_r": 0.0,
            "total_trades": 0.0
        }

    # Calculate R-multiple for each trade
    r_multiples = closed_trades_df.apply(
        lambda row: compute_r_multiple(row['entry_price'], row['exit_price'], row['stop_price']),
        axis=1
    )

    wins = r_multiples[r_multiples > 0]
    losses = r_multiples[r_multiples <= 0]  # consider scratch as loss or zero impact

    win_rate = len(wins) / len(r_multiples) if len(r_multiples) > 0 else 0.0
    loss_rate = 1.0 - win_rate

    avg_win_r = wins.mean() if not wins.empty else 0.0
    avg_loss_r = losses.mean() if not losses.empty else 0.0

    expectancy_r = (win_rate * avg_win_r) + (loss_rate * avg_loss_r)

    return {
        "win_rate": round(win_rate * 100, 1),
        "avg_win_r": round(avg_win_r, 2),
        "avg_loss_r": round(avg_loss_r, 2),
        "expectancy_r": round(expectancy_r, 2),
        "total_trades": float(len(r_multiples))
    }
