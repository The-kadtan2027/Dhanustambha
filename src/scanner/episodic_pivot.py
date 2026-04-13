"""Episodic Pivot setup detection based on gap-and-hold behavior."""

import logging
from typing import Optional

import pandas as pd

import config


logger = logging.getLogger(__name__)


def detect_episodic_pivot(
    df: pd.DataFrame,
    min_gap_pct: Optional[float] = None,
    min_gap_vol_ratio: Optional[float] = None,
    max_days_since_gap: Optional[int] = None,
) -> pd.DataFrame:
    """Detect high-volume gap-up setups that continue holding above the gap."""
    min_gap_pct = min_gap_pct or config.EP_MIN_GAP_PCT
    min_gap_vol_ratio = min_gap_vol_ratio or config.EP_MIN_GAP_VOLUME_RATIO
    max_days_since_gap = max_days_since_gap or config.EP_MAX_DAYS_SINCE_GAP

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    candidates = []

    for symbol, group in working.groupby("symbol"):
        ordered = group.sort_values("date").reset_index(drop=True)
        if len(ordered) < 25:
            continue

        today = ordered.iloc[-1]
        avg_vol_20 = ordered.iloc[-21:-1]["volume"].mean()
        if avg_vol_20 == 0:
            continue

        lookback_rows = ordered.iloc[-(max_days_since_gap + 1) : -1]
        for idx in range(len(lookback_rows) - 1, -1, -1):
            gap_row = lookback_rows.iloc[idx]
            if idx == 0:
                prev_close = (
                    ordered.iloc[-(max_days_since_gap + 2)]["close"]
                    if len(ordered) > max_days_since_gap + 2
                    else None
                )
            else:
                prev_close = lookback_rows.iloc[idx - 1]["close"]

            if prev_close is None:
                continue

            gap_pct = (gap_row["open"] - prev_close) / prev_close * 100
            gap_vol_ratio = gap_row["volume"] / avg_vol_20

            if gap_pct >= min_gap_pct and gap_vol_ratio >= min_gap_vol_ratio:
                if today["close"] >= gap_row["open"]:
                    days_since = len(lookback_rows) - idx
                    score = round(gap_pct * gap_vol_ratio, 2)
                    candidates.append(
                        {
                            "symbol": symbol,
                            "setup_type": "EPISODIC_PIVOT",
                            "pct_change": round(gap_pct, 2),
                            "volume_ratio": round(gap_vol_ratio, 2),
                            "score": score,
                            "close": round(today["close"], 2),
                            "notes": (
                                f"Gap {gap_pct:.1f}% {days_since}d ago "
                                f"on {gap_vol_ratio:.1f}x vol"
                            ),
                        }
                    )
                break

    if not candidates:
        return pd.DataFrame(
            columns=[
                "symbol",
                "setup_type",
                "pct_change",
                "volume_ratio",
                "score",
                "close",
                "notes",
            ]
        )

    return pd.DataFrame(candidates).sort_values("score", ascending=False).reset_index(
        drop=True
    )
