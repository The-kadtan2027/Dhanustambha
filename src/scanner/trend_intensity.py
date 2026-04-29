"""Trend Intensity breakout detection for steady uptrends."""

import logging
from typing import Optional

import numpy as np
import pandas as pd

import config


logger = logging.getLogger(__name__)


def _efficiency_ratio(series: pd.Series) -> float:
    """Return a simple price-path efficiency ratio for the provided series."""
    if len(series) < 2:
        return 0.0
    net_change = abs(float(series.iloc[-1] - series.iloc[0]))
    path_change = float(series.diff().abs().sum())
    if path_change == 0:
        return 0.0
    return round(net_change / path_change, 4)


def _select_benchmark_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return a local benchmark series if one is present in the scanner input."""
    benchmark_symbols = set(config.BACKTEST_BENCHMARK_CANDIDATES)
    if "symbol" not in df.columns:
        return pd.DataFrame(columns=df.columns)
    benchmark_rows = df[df["symbol"].astype(str).isin(benchmark_symbols)].copy()
    if benchmark_rows.empty:
        return benchmark_rows
    return benchmark_rows.sort_values("date").reset_index(drop=True)


def prepare_trend_intensity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Precompute reusable Trend Intensity features for every symbol/date row."""
    if df.empty:
        return df.copy()

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)
    benchmark_rows = _select_benchmark_rows(working)
    benchmark_lookup = {}
    if not benchmark_rows.empty:
        benchmark_lookup = {
            row_date: close for row_date, close in zip(benchmark_rows["date"], benchmark_rows["close"])
        }

    prepared_groups = []
    for symbol, group in working.groupby("symbol", sort=False):
        if str(symbol) in config.BACKTEST_BENCHMARK_CANDIDATES:
            continue

        ordered = group.sort_values("date").reset_index(drop=True).copy()
        ordered["ma50"] = ordered["close"].rolling(50).mean()
        ordered["ma150"] = ordered["close"].rolling(150).mean()
        ordered["ma200"] = ordered["close"].rolling(200).mean()
        ordered["atr"] = (ordered["high"] - ordered["low"]).rolling(14).mean()
        ordered["avg_vol_20"] = ordered["volume"].shift(1).rolling(20).mean()
        ordered["vol_ratio"] = ordered["volume"] / ordered["avg_vol_20"]
        ordered["lookback_high"] = ordered["close"].shift(1).rolling(config.TI_HIGH_LOOKBACK_DAYS).max()
        ordered["ma50_then"] = ordered["ma50"].shift(config.TI_MA50_TREND_LOOKBACK)
        first_valid_ma50 = ordered["ma50"].dropna().iloc[0] if ordered["ma50"].notna().any() else np.nan
        ordered["ma50_then_effective"] = ordered["ma50_then"].fillna(first_valid_ma50)
        ordered["ma50_rising"] = ordered["ma50"] > ordered["ma50_then_effective"]
        ordered["close_above_ma50"] = (ordered["close"] > ordered["ma50"]).astype(float)
        ordered["days_above_ma50_50d"] = (
            ordered["close_above_ma50"].shift(1).rolling(50).sum()
        )
        ordered["valid_ma50_count_50d"] = (
            ordered["ma50"].notna().astype(float).shift(1).rolling(50).sum()
        )
        ordered["atr_pct"] = ordered["atr"] / ordered["close"]
        ordered["pct_change"] = (
            (ordered["close"] - ordered["lookback_high"]) / ordered["lookback_high"] * 100
        )
        ordered["score"] = (
            ordered["vol_ratio"] * (ordered["ma50"] - ordered["ma50_then"]) / ordered["ma50_then"] * 100
        )
        ordered["distance_above_ma50_pct"] = (
            (ordered["close"] - ordered["ma50"]) / ordered["ma50"] * 100
        )
        ordered["distance_above_ma150_pct"] = (
            (ordered["close"] - ordered["ma150"]) / ordered["ma150"] * 100
        )
        ordered["distance_above_ma200_pct"] = (
            (ordered["close"] - ordered["ma200"]) / ordered["ma200"] * 100
        )
        ordered["ma150_above_ma200"] = ordered["ma150"] > ordered["ma200"]
        ordered["ma200_rising_20d"] = ordered["ma200"] > ordered["ma200"].shift(20)
        ordered["close_52w_high"] = ordered["high"].rolling(252, min_periods=1).max()
        ordered["within_25pct_of_52w_high"] = ordered["close"] >= ordered["close_52w_high"] * 0.75
        ordered["trend_efficiency_ratio"] = ordered["close"].rolling(20).apply(
            lambda values: _efficiency_ratio(pd.Series(values)),
            raw=False,
        )
        ordered["pullback_depth_20d"] = ordered["high"].rolling(20).max()
        ordered["pullback_depth_20d"] = (
            (ordered["pullback_depth_20d"] - ordered["low"].rolling(20).min())
            / ordered["pullback_depth_20d"]
            * 100
        )
        ordered["vol_dryup_ratio_10d"] = ordered["volume"].rolling(10).mean() / ordered["avg_vol_20"]
        ordered["setup_type"] = "TREND_INTENSITY"

        relative_strength_values = []
        for row_index, row in ordered.iterrows():
            benchmark_now = benchmark_lookup.get(row["date"])
            benchmark_then = benchmark_lookup.get(ordered.iloc[row_index - 60]["date"]) if row_index >= 60 else None
            if benchmark_now and benchmark_then and row_index >= 60:
                symbol_then = float(ordered.iloc[row_index - 60]["close"])
                symbol_return_3m = (float(row["close"]) - symbol_then) / symbol_then * 100
                benchmark_return_3m = (benchmark_now - benchmark_then) / benchmark_then * 100
                relative_strength_values.append(round(symbol_return_3m - benchmark_return_3m, 2))
            else:
                relative_strength_values.append(None)
        ordered["relative_strength_vs_benchmark_3m"] = relative_strength_values
        prepared_groups.append(ordered)

    if not prepared_groups:
        return pd.DataFrame(columns=working.columns)
    return pd.concat(prepared_groups, ignore_index=True)


def detect_trend_intensity(
    df: pd.DataFrame,
    high_lookback: Optional[int] = None,
    ma50_trend_lookback: Optional[int] = None,
    min_days_above_ma50: Optional[int] = None,
    min_vol_ratio: Optional[float] = None,
    max_atr_pct: Optional[float] = None,
) -> pd.DataFrame:
    """Detect quiet uptrends breaking to fresh highs on increased volume."""
    high_lookback = high_lookback or config.TI_HIGH_LOOKBACK_DAYS
    ma50_trend_lookback = ma50_trend_lookback or config.TI_MA50_TREND_LOOKBACK
    min_days_above_ma50 = min_days_above_ma50 or config.TI_MIN_DAYS_ABOVE_MA50
    min_vol_ratio = min_vol_ratio or config.TI_MIN_VOLUME_RATIO
    max_atr_pct = max_atr_pct or config.TI_MAX_ATR_PCT

    if {
        "ma50",
        "ma50_then",
        "days_above_ma50_50d",
        "atr_pct",
        "vol_ratio",
        "trend_efficiency_ratio",
    }.issubset(df.columns):
        prepared = df.copy()
    else:
        prepared = prepare_trend_intensity_features(df)

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
            ]
        )

    latest_date = prepared["date"].max()
    latest_rows = prepared[prepared["date"] == latest_date].copy()
    latest_rows = latest_rows.dropna(
        subset=[
            "ma50",
            "ma50_then_effective",
            "lookback_high",
            "days_above_ma50_50d",
            "valid_ma50_count_50d",
            "vol_ratio",
            "atr_pct",
        ]
    )
    filtered = latest_rows[
        latest_rows["ma50_rising"].fillna(False)
        & latest_rows["close"].gt(latest_rows["lookback_high"])
        & latest_rows["vol_ratio"].ge(min_vol_ratio)
        & latest_rows["atr_pct"].le(max_atr_pct)
    ].copy()
    filtered["required_days_above"] = filtered["valid_ma50_count_50d"].apply(
        lambda count: min(min_days_above_ma50, int(count))
    )
    filtered = filtered[filtered["days_above_ma50_50d"].ge(filtered["required_days_above"])].copy()

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
            ]
        )

    filtered["pct_change"] = filtered["pct_change"].round(2)
    filtered["volume_ratio"] = filtered["vol_ratio"].round(2)
    filtered["score"] = filtered["score"].round(2)
    filtered["close"] = filtered["close"].round(2)
    filtered["notes"] = filtered["days_above_ma50_50d"].apply(
        lambda days_above: f"New {high_lookback}d high, {int(days_above)}d above MA50"
    )
    filtered["distance_above_ma50_pct"] = filtered["distance_above_ma50_pct"].round(2)
    filtered["distance_above_ma150_pct"] = filtered["distance_above_ma150_pct"].round(2)
    filtered["distance_above_ma200_pct"] = filtered["distance_above_ma200_pct"].round(2)
    filtered["trend_efficiency_ratio"] = filtered["trend_efficiency_ratio"].round(4)
    filtered["pullback_depth_20d"] = filtered["pullback_depth_20d"].round(2)
    filtered["vol_dryup_ratio_10d"] = filtered["vol_dryup_ratio_10d"].round(2)
    filtered["days_above_ma50_50d"] = filtered["days_above_ma50_50d"].astype(int)

    candidates = filtered[
        [
            "symbol",
            "setup_type",
            "pct_change",
            "volume_ratio",
            "score",
            "close",
            "notes",
            "distance_above_ma50_pct",
            "distance_above_ma150_pct",
            "distance_above_ma200_pct",
            "ma150_above_ma200",
            "ma200_rising_20d",
            "within_25pct_of_52w_high",
            "relative_strength_vs_benchmark_3m",
            "trend_efficiency_ratio",
            "pullback_depth_20d",
            "vol_dryup_ratio_10d",
        ]
    ].copy()

    return candidates.sort_values("score", ascending=False).reset_index(drop=True)
