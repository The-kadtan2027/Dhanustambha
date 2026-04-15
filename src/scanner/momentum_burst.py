"""Momentum Burst setup detection for end-of-day OHLCV data."""

import logging
from typing import Optional

import pandas as pd

import config


logger = logging.getLogger(__name__)


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

    working = df.copy()
    working["date"] = pd.to_datetime(working["date"])
    candidates = []

    required_days = max(20, lookback + 10 + 1)

    for symbol, group in working.groupby("symbol"):
        ordered = group.sort_values("date").reset_index(drop=True)
        if len(ordered) < required_days:
            continue

        today = ordered.iloc[-1]
        if today["close"] < min_price:
            continue

        avg_vol_20 = ordered.iloc[-21:-1]["volume"].mean()
        if avg_vol_20 < min_avg_vol:
            continue

        vol_ratio = today["volume"] / avg_vol_20 if avg_vol_20 > 0 else 0
        if vol_ratio < min_vol_ratio:
            continue

        ref_close = ordered.iloc[-(lookback + 1)]["close"]
        pct_change = (today["close"] - ref_close) / ref_close * 100
        if not (min_pct <= pct_change <= max_pct):
            continue

        prior_window = ordered.iloc[-(lookback + 11) : -(lookback + 1)]
        if len(prior_window) == 10:
            prior_start_close = prior_window.iloc[0]["close"]
            prior_end_close = prior_window.iloc[-1]["close"]
            prior_run_pct = (prior_end_close - prior_start_close) / prior_start_close * 100
            if prior_run_pct > max_prior_run:
                logger.debug(
                    "Skipping %s because it already ran %.1f%% before the burst",
                    symbol,
                    prior_run_pct,
                )
                continue

        score = round(pct_change * vol_ratio, 2)
        candidates.append(
            {
                "symbol": symbol,
                "setup_type": "MOMENTUM_BURST",
                "pct_change": round(pct_change, 2),
                "volume_ratio": round(vol_ratio, 2),
                "score": score,
                "close": round(today["close"], 2),
                "notes": f"{pct_change:.1f}% on {vol_ratio:.1f}x volume",
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

    result = pd.DataFrame(candidates)
    return result.sort_values("score", ascending=False).reset_index(drop=True)
