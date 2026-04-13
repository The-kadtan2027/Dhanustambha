"""Trend Intensity breakout detection for steady uptrends."""

import logging
from typing import Optional

import pandas as pd

import config


logger = logging.getLogger(__name__)


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

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    candidates = []

    required_days = max(52, high_lookback + 5)

    for symbol, group in working.groupby("symbol"):
        ordered = group.sort_values("date").reset_index(drop=True)
        if len(ordered) < required_days:
            continue

        ordered["ma50"] = ordered["close"].rolling(50).mean()
        ordered["atr"] = (ordered["high"] - ordered["low"]).rolling(14).mean()

        today = ordered.iloc[-1]
        if pd.isna(today["ma50"]):
            continue

        ma50_now = today["ma50"]
        prior_ma50_window = ordered.iloc[: -1]["ma50"].dropna()
        if prior_ma50_window.empty:
            continue

        if len(prior_ma50_window) > ma50_trend_lookback:
            ma50_then = prior_ma50_window.iloc[-ma50_trend_lookback - 1]
        else:
            ma50_then = prior_ma50_window.iloc[0]

        if ma50_now <= ma50_then:
            continue

        lookback_closes = ordered.iloc[-(high_lookback + 1) : -1]["close"].max()
        if today["close"] <= lookback_closes:
            continue

        last_50 = ordered.iloc[-51:-1]
        valid_ma50 = last_50["ma50"].notna()
        days_above = (last_50.loc[valid_ma50, "close"] > last_50.loc[valid_ma50, "ma50"]).sum()
        required_days_above = min(min_days_above_ma50, int(valid_ma50.sum()))
        if days_above < required_days_above:
            continue

        avg_vol_20 = ordered.iloc[-21:-1]["volume"].mean()
        if avg_vol_20 == 0:
            continue

        vol_ratio = today["volume"] / avg_vol_20
        if vol_ratio < min_vol_ratio:
            continue

        atr_pct = today["atr"] / today["close"] if today["close"] > 0 else 1.0
        if not pd.isna(atr_pct) and atr_pct > max_atr_pct:
            continue

        score = round(vol_ratio * (ma50_now - ma50_then) / ma50_then * 100, 2)
        candidates.append(
            {
                "symbol": symbol,
                "setup_type": "TREND_INTENSITY",
                "pct_change": round(
                    (today["close"] - lookback_closes) / lookback_closes * 100, 2
                ),
                "volume_ratio": round(vol_ratio, 2),
                "score": score,
                "close": round(today["close"], 2),
                "notes": f"New {high_lookback}d high, {days_above}d above MA50",
            }
        )

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
