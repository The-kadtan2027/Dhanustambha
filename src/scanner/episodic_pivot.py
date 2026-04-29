"""Episodic Pivot setup detection based on gap-and-hold behavior."""

import logging
from typing import Optional

import numpy as np
import pandas as pd

import config


logger = logging.getLogger(__name__)


def _classify_ep_tier(row: pd.Series) -> str:
    """Classify an EP candidate as tier 'A+' or 'B' based on config thresholds.

    A+ requires:
      - gap_pct >= EP_TIER_A_MIN_GAP_PCT
      - gap_vol_ratio >= EP_TIER_A_MIN_GAP_VOLUME_RATIO
      - days_since_gap <= EP_TIER_A_MAX_DAYS_SINCE_GAP
    Everything else is tier B.
    """
    if (
        row.get("gap_pct", 0) >= config.EP_TIER_A_MIN_GAP_PCT
        and row.get("gap_vol_ratio", 0) >= config.EP_TIER_A_MIN_GAP_VOLUME_RATIO
        and row.get("days_since_gap", 999) <= config.EP_TIER_A_MAX_DAYS_SINCE_GAP
    ):
        return "A+"
    return "B"


def _close_location_pct(high: float, low: float, close: float) -> float:
    """Return where the close sits within the day's range as a percentage."""
    day_range = high - low
    if day_range <= 0:
        return 50.0
    return round((close - low) / day_range * 100, 2)


def prepare_episodic_pivot_features(df: pd.DataFrame) -> pd.DataFrame:
    """Precompute reusable Episodic Pivot features for every symbol/date row."""
    if df.empty:
        return df.copy()

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)

    prepared_groups = []
    for _, group in working.groupby("symbol", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True).copy()
        ordered["prev_close"] = ordered["close"].shift(1)
        ordered["avg_vol_20_gap"] = ordered["volume"].shift(1).rolling(20).mean()
        ordered["gap_pct"] = (ordered["open"] - ordered["prev_close"]) / ordered["prev_close"] * 100
        ordered["gap_vol_ratio"] = ordered["volume"] / ordered["avg_vol_20_gap"]
        ordered["gap_day_close_location_pct"] = np.where(
            (ordered["high"] - ordered["low"]) > 0,
            ((ordered["close"] - ordered["low"]) / (ordered["high"] - ordered["low"]) * 100).round(2),
            50.0,
        )
        ordered["gap_day_close_vs_open_pct"] = (
            (ordered["close"] - ordered["open"]) / ordered["open"] * 100
        )

        ordered["prior_65d_run_pct"] = (
            (ordered["close"].shift(1) - ordered["close"].shift(65)) / ordered["close"].shift(65) * 100
        )
        prior_65d_high = ordered["high"].shift(1).rolling(65).max()
        prior_65d_low = ordered["low"].shift(1).rolling(65).min()
        ordered["prior_65d_weakness_pct"] = (
            (prior_65d_high - prior_65d_low) / prior_65d_high * 100
        )
        prior_252_high = ordered["high"].shift(1).rolling(252, min_periods=1).max()
        ordered["distance_to_52w_high_before_gap"] = (
            (prior_252_high - ordered["prev_close"]) / prior_252_high * 100
        )

        gap_open = ordered["open"].where(ordered["gap_pct"] > 0)
        ordered["holding_above_gap_open_days"] = (
            (ordered["close"] >= gap_open).astype(float)
        )
        ordered["holding_above_gap_open_days"] = (
            ordered["holding_above_gap_open_days"]
            .where(gap_open.notna())
        )

        previous_gap_fill = ordered["prev_close"]
        gap_size = gap_open - previous_gap_fill
        ordered["gap_fill_pct"] = np.where(
            gap_size > 0,
            ((gap_open - ordered["low"]) / gap_size).clip(lower=0, upper=1) * 100,
            np.nan,
        )

        recent_gap_flag = ordered["gap_pct"].ge(0).astype(int)
        qualifying_gap_flag = (
            ordered["gap_pct"].fillna(-np.inf).ge(4.0).astype(int)
        )
        ordered["prior_gap_count_126"] = qualifying_gap_flag.shift(1).rolling(126, min_periods=1).sum()
        ordered["is_first_gap_in_6m"] = ordered["prior_gap_count_126"].fillna(0).eq(0)
        prepared_groups.append(ordered)

    return pd.concat(prepared_groups, ignore_index=True)


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

    if {
        "gap_pct",
        "gap_vol_ratio",
        "avg_vol_20_gap",
        "prior_65d_run_pct",
        "is_first_gap_in_6m",
    }.issubset(df.columns):
        prepared = df.copy()
    else:
        prepared = prepare_episodic_pivot_features(df)

    prepared["date"] = pd.to_datetime(prepared["date"])
    if prepared.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "setup_type",
                "pct_change",
                "volume_ratio",
                "score",
                "close",
                "notes",
                "ep_tier",
            ]
        )

    latest_date = prepared["date"].max()
    candidates = []

    for symbol, group in prepared.groupby("symbol", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True)
        if len(ordered) < 25:
            continue

        today = ordered.iloc[-1]
        recent_window = ordered.iloc[-(max_days_since_gap + 1) :].copy()
        if recent_window.empty:
            continue

        window_start = len(ordered) - len(recent_window)
        for idx in range(len(recent_window) - 1, -1, -1):
            gap_row = recent_window.iloc[idx]
            if pd.isna(gap_row.get("gap_pct")) or pd.isna(gap_row.get("gap_vol_ratio")):
                continue

            if gap_row["gap_pct"] >= min_gap_pct and gap_row["gap_vol_ratio"] >= min_gap_vol_ratio:
                if today["close"] >= gap_row["open"]:
                    gap_position = window_start + idx
                    days_since = len(ordered) - 1 - gap_position
                    score = round(float(gap_row["gap_pct"]) * float(gap_row["gap_vol_ratio"]), 2)
                    hold_window = ordered.iloc[gap_position + 1 :]
                    holding_days = int((hold_window["close"] >= gap_row["open"]).sum()) if not hold_window.empty else 0
                    candidates.append(
                        {
                            "symbol": symbol,
                            "setup_type": "EPISODIC_PIVOT",
                            "pct_change": round(float(gap_row["gap_pct"]), 2),
                            "volume_ratio": round(float(gap_row["gap_vol_ratio"]), 2),
                            "score": score,
                            "close": round(float(today["close"]), 2),
                            "notes": (
                                f"Gap {float(gap_row['gap_pct']):.1f}% {days_since}d ago "
                                f"on {float(gap_row['gap_vol_ratio']):.1f}x vol"
                            ),
                            "days_since_gap": int(days_since),
                            "gap_pct": round(float(gap_row["gap_pct"]), 2),
                            "gap_vol_ratio": round(float(gap_row["gap_vol_ratio"]), 2),
                            "gap_day_close_location_pct": round(float(gap_row["gap_day_close_location_pct"]), 2),
                            "gap_day_close_vs_open_pct": round(float(gap_row["gap_day_close_vs_open_pct"]), 2),
                            "prior_65d_run_pct": round(float(gap_row["prior_65d_run_pct"]), 2)
                            if pd.notna(gap_row["prior_65d_run_pct"])
                            else 0.0,
                            "prior_65d_weakness_pct": round(float(gap_row["prior_65d_weakness_pct"]), 2)
                            if pd.notna(gap_row["prior_65d_weakness_pct"])
                            else 0.0,
                            "distance_to_52w_high_before_gap": round(
                                float(gap_row["distance_to_52w_high_before_gap"]),
                                2,
                            )
                            if pd.notna(gap_row["distance_to_52w_high_before_gap"])
                            else 0.0,
                            "holding_above_gap_open_days": holding_days,
                            "gap_fill_pct": round(float(gap_row["gap_fill_pct"]), 2)
                            if pd.notna(gap_row["gap_fill_pct"])
                            else 0.0,
                            "is_first_gap_in_6m": bool(gap_row["is_first_gap_in_6m"]),
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
                "ep_tier",
            ]
        )

    result = pd.DataFrame(candidates).sort_values("score", ascending=False).reset_index(drop=True)
    result["ep_tier"] = result.apply(_classify_ep_tier, axis=1)
    return result
