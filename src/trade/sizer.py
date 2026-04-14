"""Position sizing module for Phase 2 Trade Management."""

import logging
from typing import Dict, Optional

import config


logger = logging.getLogger(__name__)


def calculate_position_size(
    account_size: float,
    entry_price: float,
    stop_price: float,
    market_verdict: str = "OFFENSIVE",
) -> Optional[Dict[str, float]]:
    """Calculate position size from account risk and hard caps."""
    if entry_price <= 0 or stop_price <= 0:
        logger.warning("Prices must be positive. Entry: %s, Stop: %s", entry_price, stop_price)
        return None

    if stop_price >= entry_price:
        logger.warning("Stop price (%s) must be below entry price (%s)", stop_price, entry_price)
        return None

    stop_distance = entry_price - stop_price
    risk_per_trade = account_size * config.TRADE_RISK_PCT
    shares = int(risk_per_trade // stop_distance)
    if shares == 0:
        logger.warning(
            "Calculated shares is 0. Risk: %s, Stop Dist: %s. Capital too small or stop too wide.",
            risk_per_trade,
            stop_distance,
        )
        return None

    position_value = shares * entry_price
    max_allowed_position = account_size * config.TRADE_MAX_POSITION_PCT
    if position_value > max_allowed_position:
        logger.debug(
            "Position capped by max position limit (10%% of account). Was size: %s, Max: %s",
            position_value,
            max_allowed_position,
        )
        shares = int(max_allowed_position // entry_price)
        if shares == 0:
            return None
        position_value = shares * entry_price

    if market_verdict.upper() == "DEFENSIVE":
        logger.info("DEFENSIVE market regime active - halving final position size.")
        shares = max(int(shares * config.TRADE_DEFENSIVE_SIZE_FACTOR), 1)
        position_value = shares * entry_price

    actual_risk = shares * stop_distance
    return {
        "shares": float(shares),
        "position_value": round(position_value, 2),
        "risk_amount": round(actual_risk, 2),
        "r_unit": round(stop_distance, 2),
    }
