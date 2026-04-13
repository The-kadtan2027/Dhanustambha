"""Market breadth metric computation for the latest available trading day."""

import logging
from typing import Dict

import pandas as pd


logger = logging.getLogger(__name__)


def compute_breadth(df: pd.DataFrame) -> Dict:
    """Compute breadth metrics from a multi-symbol OHLCV DataFrame."""
    if df.empty:
        logger.error("Empty DataFrame passed to compute_breadth")
        return {}

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    latest_date = working["date"].max()

    results = []
    for symbol, group in working.groupby("symbol"):
        ordered = group.sort_values("date").reset_index(drop=True)
        if len(ordered) < 21:
            continue

        ordered["ma20"] = ordered["close"].rolling(20).mean()
        ordered["ma50"] = (
            ordered["close"].rolling(50).mean() if len(ordered) >= 51 else float("nan")
        )
        ordered["high_52w"] = ordered["high"].rolling(min(252, len(ordered))).max()
        ordered["low_52w"] = ordered["low"].rolling(min(252, len(ordered))).min()

        today = ordered[ordered["date"] == latest_date]
        if today.empty:
            continue

        row = today.iloc[0]
        previous_rows = ordered[ordered["date"] < latest_date]
        previous = previous_rows.iloc[-1] if not previous_rows.empty else None

        results.append(
            {
                "symbol": symbol,
                "close": row["close"],
                "prev_close": previous["close"] if previous is not None else row["close"],
                "volume": row["volume"],
                "above_ma20": int(
                    not pd.isna(row["ma20"]) and row["close"] > row["ma20"]
                ),
                "above_ma50": int(
                    not pd.isna(row["ma50"]) and row["close"] > row["ma50"]
                ),
                "new_52w_high": int(
                    not pd.isna(row["high_52w"]) and row["high"] >= row["high_52w"]
                ),
                "new_52w_low": int(
                    not pd.isna(row["low_52w"]) and row["low"] <= row["low_52w"]
                ),
            }
        )

    if not results:
        logger.warning("No results computed in compute_breadth due to insufficient data")
        return {}

    result_df = pd.DataFrame(results)
    total = len(result_df)
    advancing = int((result_df["close"] > result_df["prev_close"]).sum())
    declining = int((result_df["close"] < result_df["prev_close"]).sum())
    up_volume = result_df.loc[result_df["close"] >= result_df["prev_close"], "volume"].sum()
    total_volume = result_df["volume"].sum()
    up_volume_ratio = round(up_volume / total_volume, 4) if total_volume > 0 else 0.0

    return {
        "date": latest_date.strftime("%Y-%m-%d"),
        "pct_above_ma20": round(result_df["above_ma20"].sum() / total * 100, 2),
        "pct_above_ma50": round(result_df["above_ma50"].sum() / total * 100, 2),
        "new_highs_52w": int(result_df["new_52w_high"].sum()),
        "new_lows_52w": int(result_df["new_52w_low"].sum()),
        "up_volume_ratio": up_volume_ratio,
        "advancing": advancing,
        "declining": declining,
    }
