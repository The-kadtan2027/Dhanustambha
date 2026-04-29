"""Market breadth metric computation for the latest available trading day."""

import logging
from typing import Dict

import pandas as pd


logger = logging.getLogger(__name__)


def compute_historical_breadth(df: pd.DataFrame) -> pd.DataFrame:
    """Compute breadth metrics for every eligible trading day in the OHLCV history."""
    if df.empty:
        logger.error("Empty DataFrame passed to compute_historical_breadth")
        return pd.DataFrame(
            columns=[
                "date",
                "pct_above_ma20",
                "pct_above_ma50",
                "new_highs_52w",
                "new_lows_52w",
                "up_volume_ratio",
                "advancing",
                "declining",
            ]
        )

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)
    working["row_number"] = working.groupby("symbol").cumcount() + 1
    working = working[working["row_number"] >= 21].copy()
    if working.empty:
        logger.warning(
            "No eligible history in compute_historical_breadth due to insufficient lookback"
        )
        return pd.DataFrame(
            columns=[
                "date",
                "pct_above_ma20",
                "pct_above_ma50",
                "new_highs_52w",
                "new_lows_52w",
                "up_volume_ratio",
                "advancing",
                "declining",
            ]
        )

    close_by_symbol = working.groupby("symbol")["close"]
    high_by_symbol = working.groupby("symbol")["high"]
    low_by_symbol = working.groupby("symbol")["low"]
    working["ma20"] = close_by_symbol.transform(lambda values: values.rolling(20).mean())
    working["ma50"] = close_by_symbol.transform(lambda values: values.rolling(50).mean())
    working["high_52w"] = high_by_symbol.transform(
        lambda values: values.rolling(252, min_periods=1).max()
    )
    working["low_52w"] = low_by_symbol.transform(
        lambda values: values.rolling(252, min_periods=1).min()
    )
    working["prev_close"] = close_by_symbol.shift(1).fillna(working["close"])
    working["above_ma20"] = (
        (~working["ma20"].isna()) & (working["close"] > working["ma20"])
    ).astype(int)
    working["above_ma50"] = (
        (~working["ma50"].isna()) & (working["close"] > working["ma50"])
    ).astype(int)
    working["new_52w_high"] = (
        (~working["high_52w"].isna()) & (working["high"] >= working["high_52w"])
    ).astype(int)
    working["new_52w_low"] = (
        (~working["low_52w"].isna()) & (working["low"] <= working["low_52w"])
    ).astype(int)
    working["up_volume"] = working["volume"].where(
        working["close"] >= working["prev_close"],
        0,
    )
    working["advancing_flag"] = (working["close"] > working["prev_close"]).astype(int)
    working["declining_flag"] = (working["close"] < working["prev_close"]).astype(int)

    grouped = (
        working.groupby("date", as_index=False)
        .agg(
            total_symbols=("symbol", "count"),
            above_ma20=("above_ma20", "sum"),
            above_ma50=("above_ma50", "sum"),
            new_highs_52w=("new_52w_high", "sum"),
            new_lows_52w=("new_52w_low", "sum"),
            up_volume=("up_volume", "sum"),
            total_volume=("volume", "sum"),
            advancing=("advancing_flag", "sum"),
            declining=("declining_flag", "sum"),
        )
        .sort_values("date")
        .reset_index(drop=True)
    )
    grouped["pct_above_ma20"] = round(grouped["above_ma20"] / grouped["total_symbols"] * 100, 2)
    grouped["pct_above_ma50"] = round(grouped["above_ma50"] / grouped["total_symbols"] * 100, 2)
    grouped["up_volume_ratio"] = (
        grouped["up_volume"] / grouped["total_volume"]
    ).fillna(0.0).round(4)
    return grouped[
        [
            "date",
            "pct_above_ma20",
            "pct_above_ma50",
            "new_highs_52w",
            "new_lows_52w",
            "up_volume_ratio",
            "advancing",
            "declining",
        ]
    ]


def compute_breadth(df: pd.DataFrame) -> Dict:
    """Compute breadth metrics from a multi-symbol OHLCV DataFrame."""
    if df.empty:
        logger.error("Empty DataFrame passed to compute_breadth")
        return {}

    historical = compute_historical_breadth(df)
    if historical.empty:
        logger.warning("No results computed in compute_breadth due to insufficient data")
        return {}
    latest_row = historical.iloc[-1]
    return {
        "date": latest_row["date"].strftime("%Y-%m-%d"),
        "pct_above_ma20": float(latest_row["pct_above_ma20"]),
        "pct_above_ma50": float(latest_row["pct_above_ma50"]),
        "new_highs_52w": int(latest_row["new_highs_52w"]),
        "new_lows_52w": int(latest_row["new_lows_52w"]),
        "up_volume_ratio": float(latest_row["up_volume_ratio"]),
        "advancing": int(latest_row["advancing"]),
        "declining": int(latest_row["declining"]),
    }
