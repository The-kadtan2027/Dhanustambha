"""Momentum Burst setup detection for end-of-day OHLCV data."""

import logging
from typing import Optional

import numpy as np
import pandas as pd

import config


logger = logging.getLogger(__name__)


def _classify_mb_quality(row: pd.Series) -> str:
    """Classify an MB candidate as 'HIGH' or 'STANDARD' quality.

    HIGH requires all three research-validated filters:
      - nr_count_10d >= MB_QUALITY_MIN_NR_COUNT (tight consolidation base)
      - close_location_pct >= MB_QUALITY_MIN_CLOSE_LOC_PCT (strong close)
      - distance_from_20d_high_pct >= MB_QUALITY_MIN_DIST_20D_HIGH (breakout)
    Everything else is STANDARD.
    """
    if (
        row.get("nr_count_10d", 0) >= config.MB_QUALITY_MIN_NR_COUNT
        and row.get("close_location_pct", 0) >= config.MB_QUALITY_MIN_CLOSE_LOC_PCT
        and row.get("distance_from_20d_high_pct", -999) >= config.MB_QUALITY_MIN_DIST_20D_HIGH
    ):
        return "HIGH"
    return "STANDARD"


def _close_location_pct(high: float, low: float, close: float) -> float:
    """Return where the close sits within the day's range as a percentage."""
    day_range = high - low
    if day_range <= 0:
        return 50.0
    return round((close - low) / day_range * 100, 2)


def _trend_linearity(series: pd.Series) -> float:
    """Return the R-squared of a simple linear fit over the provided close series."""
    if len(series) < 2:
        return 0.0
    x_values = np.arange(len(series), dtype=float)
    y_values = series.astype(float).to_numpy()
    correlation = np.corrcoef(x_values, y_values)[0, 1]
    if np.isnan(correlation):
        return 0.0
    return round(float(correlation ** 2), 4)


def prepare_momentum_burst_features(
    df: pd.DataFrame,
    lookback: Optional[int] = None,
) -> pd.DataFrame:
    """Precompute reusable Momentum Burst features for every symbol/date row."""
    lookback = lookback or config.MB_LOOKBACK_DAYS
    if df.empty:
        return df.copy()

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)

    prepared_groups = []
    for symbol, group in working.groupby("symbol", sort=False):
        ordered = group.sort_values("date").reset_index(drop=True).copy()
        ordered["avg_vol_20"] = ordered["volume"].shift(1).rolling(20).mean()
        ordered["vol_ratio"] = ordered["volume"] / ordered["avg_vol_20"]
        ordered["ref_close"] = ordered["close"].shift(lookback)
        ordered["pct_change"] = (ordered["close"] - ordered["ref_close"]) / ordered["ref_close"] * 100

        prior_10d_start = ordered["close"].shift(lookback + 10)
        prior_10d_end = ordered["close"].shift(lookback + 1)
        ordered["prior_10d_run_pct"] = (
            (prior_10d_end - prior_10d_start) / prior_10d_start * 100
        )

        prior_20d_start = ordered["close"].shift(lookback + 20)
        prior_20d_end = ordered["close"].shift(lookback + 1)
        ordered["prior_20d_run_pct"] = (
            (prior_20d_end - prior_20d_start) / prior_20d_start * 100
        )

        day_range = (ordered["high"] - ordered["low"]).astype(float)
        ordered["close_location_pct"] = np.where(
            day_range > 0,
            ((ordered["close"] - ordered["low"]) / day_range * 100).round(2),
            50.0,
        )
        ordered["avg_range_20"] = day_range.shift(1).rolling(20).mean()
        ordered["range_expansion_ratio"] = (
            day_range / ordered["avg_range_20"]
        ).replace([np.inf, -np.inf], np.nan)
        ordered["distance_from_20d_high_pct"] = (
            (ordered["close"] - ordered["high"].shift(1).rolling(20).max())
            / ordered["high"].shift(1).rolling(20).max()
            * 100
        )

        quiet_flags = (
            ordered["close"].pct_change().abs().fillna(0).le(0.02).astype(int).shift(1)
        )
        ordered["consolidation_days"] = quiet_flags.rolling(10).sum()

        shifted_ranges = day_range.shift(1)
        ordered["nr_count_10d"] = shifted_ranges.rolling(10).apply(
            lambda values: float((values <= np.median(values)).sum()),
            raw=True,
        )
        ordered["trend_linearity_20d"] = ordered["close"].rolling(20).apply(
            lambda values: _trend_linearity(pd.Series(values)),
            raw=False,
        )
        ordered["score"] = (ordered["pct_change"] * ordered["vol_ratio"]).round(2)
        ordered["setup_type"] = "MOMENTUM_BURST"
        prepared_groups.append(ordered)

    return pd.concat(prepared_groups, ignore_index=True)


def detect_momentum_burst(
    df: pd.DataFrame,
    min_pct: Optional[float] = None,
    max_pct: Optional[float] = None,
    min_vol_ratio: Optional[float] = None,
    lookback: Optional[int] = None,
    min_price: Optional[float] = None,
    min_avg_vol: Optional[int] = None,
    max_prior_run: Optional[float] = None,
) -> pd.DataFrame:
    """Scan OHLCV history for Momentum Burst setups and rank valid candidates."""
    min_pct = min_pct or config.MB_MIN_PCT_CHANGE
    max_pct = max_pct or config.MB_MAX_PCT_CHANGE
    min_vol_ratio = min_vol_ratio or config.MB_MIN_VOLUME_RATIO
    lookback = lookback or config.MB_LOOKBACK_DAYS
    min_price = min_price or config.MB_MIN_PRICE
    min_avg_vol = min_avg_vol or config.MB_MIN_AVG_VOLUME
    max_prior_run = max_prior_run or config.MB_MAX_PRIOR_RUN

    if {
        "avg_vol_20",
        "vol_ratio",
        "prior_10d_run_pct",
        "nr_count_10d",
        "consolidation_days",
        "trend_linearity_20d",
    }.issubset(df.columns):
        prepared = df.copy()
    else:
        prepared = prepare_momentum_burst_features(df, lookback=lookback)

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
                "mb_quality",
            ]
        )

    latest_date = prepared["date"].max()
    latest_rows = prepared[prepared["date"] == latest_date].copy()
    latest_rows = latest_rows.dropna(
        subset=[
            "avg_vol_20",
            "vol_ratio",
            "pct_change",
            "prior_10d_run_pct",
        ]
    )

    filtered = latest_rows[
        latest_rows["close"].ge(min_price)
        & latest_rows["avg_vol_20"].ge(min_avg_vol)
        & latest_rows["vol_ratio"].ge(min_vol_ratio)
        & latest_rows["pct_change"].between(min_pct, max_pct)
        & latest_rows["prior_10d_run_pct"].le(max_prior_run)
    ].copy()

    if filtered.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "setup_type",
                "pct_change",
                "volume_ratio",
                "score",
                "close",
                "notes",
                "mb_quality",
            ]
        )

    filtered["pct_change"] = filtered["pct_change"].round(2)
    filtered["volume_ratio"] = filtered["vol_ratio"].round(2)
    filtered["close"] = filtered["close"].round(2)
    filtered["score"] = filtered["score"].round(2)
    filtered["notes"] = filtered.apply(
        lambda row: f"{row['pct_change']:.1f}% on {row['volume_ratio']:.1f}x volume",
        axis=1,
    )
    filtered["nr_count_10d"] = filtered["nr_count_10d"].fillna(0).astype(int)
    filtered["consolidation_days"] = filtered["consolidation_days"].fillna(0).astype(int)
    filtered["prior_10d_run_pct"] = filtered["prior_10d_run_pct"].round(2)
    filtered["prior_20d_run_pct"] = filtered["prior_20d_run_pct"].round(2)
    filtered["distance_from_20d_high_pct"] = filtered["distance_from_20d_high_pct"].round(2)
    filtered["trend_linearity_20d"] = filtered["trend_linearity_20d"].round(4)
    filtered["range_expansion_ratio"] = filtered["range_expansion_ratio"].round(2)

    candidates = filtered[
        [
            "symbol",
            "setup_type",
            "pct_change",
            "volume_ratio",
            "score",
            "close",
            "notes",
            "close_location_pct",
            "range_expansion_ratio",
            "nr_count_10d",
            "consolidation_days",
            "prior_10d_run_pct",
            "prior_20d_run_pct",
            "distance_from_20d_high_pct",
            "trend_linearity_20d",
        ]
    ].copy()

    candidates["mb_quality"] = candidates.apply(_classify_mb_quality, axis=1)
    return candidates.sort_values("score", ascending=False).reset_index(drop=True)
