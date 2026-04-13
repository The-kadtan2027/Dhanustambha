"""Market condition verdict rules based on computed breadth metrics."""

import logging
from typing import Dict

import config


logger = logging.getLogger(__name__)


def compute_verdict(metrics: Dict) -> str:
    """Return OFFENSIVE, DEFENSIVE, or AVOID from breadth metrics."""
    if not metrics:
        logger.warning("Empty metrics passed to compute_verdict; returning AVOID")
        return "AVOID"

    pct_ma20 = metrics.get("pct_above_ma20", 0)
    up_volume = metrics.get("up_volume_ratio", 0)
    highs = metrics.get("new_highs_52w", 0)
    lows = metrics.get("new_lows_52w", 1)

    if (
        pct_ma20 >= config.MM_OFFENSIVE_MA20_PCT
        and up_volume >= config.MM_OFFENSIVE_UPVOL_RATIO
        and highs >= lows * config.MM_OFFENSIVE_HIGHS_VS_LOWS
    ):
        return "OFFENSIVE"

    if pct_ma20 >= config.MM_DEFENSIVE_MA20_PCT and highs >= lows:
        return "DEFENSIVE"

    return "AVOID"
