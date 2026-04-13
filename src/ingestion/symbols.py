"""Symbol universe definitions for Dhanustambha.

Universe loading strategy:
  1. Try to download the official NSE constituent CSV for the requested index.
  2. Cache it locally in data/universe_cache/ (refresh every UNIVERSE_REFRESH_DAYS).
  3. If the download fails, fall back to the cached file if one exists.
  4. NIFTY50 is always hardcoded as the dev/test fallback (fast, no network needed).

NSE constituent CSV URLs (unauthenticated, plain CSV):
  NIFTY 50        : https://archives.nseindia.com/content/indices/ind_nifty50list.csv
  NIFTY 500       : https://archives.nseindia.com/content/indices/ind_nifty500list.csv
  Midcap 150      : https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv
  Smallcap 250    : https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv

The combined NIFTY750 universe = deduplicated NIFTY500 + Smallcap250.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import requests

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hardcoded NIFTY 50 — used as dev/test fallback and never needs a network call
# Composition as of April 2026 (NSE official).
# ---------------------------------------------------------------------------
NIFTY50: List[str] = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "BAJFINANCE", "NTPC", "POWERGRID", "ULTRACEMCO",
    "NESTLEIND", "WIPRO", "HCLTECH", "TECHM", "ONGC",
    "JSWSTEEL", "TATAMOTORS", "TATASTEEL", "ADANIPORTS", "GRASIM",
    "CIPLA", "DIVISLAB", "DRREDDY", "EICHERMOT", "BAJAJFINSV",
    "BAJAJ-AUTO", "BPCL", "BRITANNIA", "COALINDIA", "HEROMOTOCO",
    "HINDALCO", "INDUSINDBK", "M&M", "SBILIFE", "SHRIRAMFIN",
    "TATACONSUM", "UPL", "VEDL", "ADANIENT", "APOLLOHOSP",
]

NIFTY50_TEST: List[str] = NIFTY50[:10]

# NSE constituent CSV download URLs (no auth required)
_NSE_CONSTITUENT_URLS: Dict[str, str] = {
    "NIFTY50":      "https://archives.nseindia.com/content/indices/ind_nifty50list.csv",
    "NIFTY500":     "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
    "MIDCAP150":    "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv",
    "SMALLCAP250":  "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv",
}

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nseindia.com",
    "Accept-Language": "en-US,en;q=0.9",
}


def _cache_path(index_name: str) -> str:
    """Return the local cache file path for an index constituent CSV."""
    os.makedirs(config.UNIVERSE_CACHE_DIR, exist_ok=True)
    return os.path.join(config.UNIVERSE_CACHE_DIR, f"{index_name}.csv")


def _cache_is_fresh(index_name: str) -> bool:
    """Return True if the cached file exists and is younger than UNIVERSE_REFRESH_DAYS."""
    path = _cache_path(index_name)
    if not os.path.exists(path):
        return False
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    return age < timedelta(days=config.UNIVERSE_REFRESH_DAYS)


def _download_nse_constituent_csv(index_name: str) -> Optional[pd.DataFrame]:
    """Download the NSE constituent CSV for the given index name. Returns DataFrame or None."""
    url = _NSE_CONSTITUENT_URLS.get(index_name)
    if not url:
        logger.error("No URL configured for index '%s'", index_name)
        return None
    try:
        resp = requests.get(url, headers=_NSE_HEADERS, timeout=config.DATA_FETCH_TIMEOUT_SECONDS)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        logger.info("Downloaded %d rows from NSE constituent CSV for %s", len(df), index_name)
        return df
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to download NSE constituent CSV for %s: %s", index_name, exc)
        return None


def _parse_symbol_column(df: pd.DataFrame) -> List[str]:
    """Extract and clean the 'Symbol' column from an NSE constituent CSV."""
    # NSE CSVs use 'Symbol' as the column name
    col = next((c for c in df.columns if c.strip().lower() == "symbol"), None)
    if col is None:
        logger.error("Could not find 'Symbol' column in constituent CSV. Columns: %s", df.columns.tolist())
        return []
    symbols = [str(s).strip().upper() for s in df[col].dropna()]
    # Filter out blank or obviously invalid entries
    symbols = [s for s in symbols if s and s != "NAN" and len(s) <= 20]
    return symbols


def load_index_symbols(index_name: str) -> List[str]:
    """Load symbols for an NSE index, using cache when fresh, download when stale.

    Args:
        index_name: One of 'NIFTY50', 'NIFTY500', 'MIDCAP150', 'SMALLCAP250'.

    Returns:
        List of NSE symbol strings, e.g. ['RELIANCE', 'TCS', ...].
        Falls back to NIFTY50 hardcoded list if all else fails.
    """
    cache_file = _cache_path(index_name)

    # 1. Fresh cache — use it directly
    if _cache_is_fresh(index_name):
        logger.debug("Using fresh cache for %s: %s", index_name, cache_file)
        try:
            df = pd.read_csv(cache_file)
            symbols = _parse_symbol_column(df)
            if symbols:
                logger.info("Loaded %d symbols for %s from cache", len(symbols), index_name)
                return symbols
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read cache for %s: %s", index_name, exc)

    # 2. Download from NSE
    df = _download_nse_constituent_csv(index_name)
    if df is not None:
        symbols = _parse_symbol_column(df)
        if symbols:
            # Save to cache
            try:
                df.to_csv(cache_file, index=False)
                logger.info("Saved %d symbols for %s to cache", len(symbols), index_name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not write cache for %s: %s", index_name, exc)
            return symbols

    # 3. Stale cache as last resort
    if os.path.exists(cache_file):
        logger.warning("Download failed; using stale cache for %s", index_name)
        try:
            df = pd.read_csv(cache_file)
            symbols = _parse_symbol_column(df)
            if symbols:
                return symbols
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to read stale cache for %s: %s", index_name, exc)

    # 4. Hard fallback
    logger.error("All sources failed for %s; falling back to hardcoded NIFTY50", index_name)
    return NIFTY50


def get_universe_symbols(universe: str = "NIFTY500") -> List[str]:
    """Return the symbol list for the requested universe.

    Args:
        universe: One of 'NIFTY50', 'NIFTY50_TEST', 'NIFTY500', 'NIFTY750'.
                  'NIFTY750' = deduplicated union of NIFTY500 + SMALLCAP250.

    Returns:
        Sorted, deduplicated list of NSE symbol strings.
    """
    # Fast hardcoded paths — no I/O
    if universe == "NIFTY50":
        return list(NIFTY50)
    if universe == "NIFTY50_TEST":
        return list(NIFTY50_TEST)

    # Dynamic paths — use cache / download
    if universe == "NIFTY500":
        return load_index_symbols("NIFTY500")

    if universe == "NIFTY750":
        nifty500 = load_index_symbols("NIFTY500")
        smallcap250 = load_index_symbols("SMALLCAP250")
        combined = sorted(set(nifty500) | set(smallcap250))
        logger.info("NIFTY750 universe: %d symbols (NIFTY500=%d, SC250=%d, overlap=%d)",
                    len(combined), len(nifty500), len(smallcap250),
                    len(set(nifty500) & set(smallcap250)))
        return combined

    logger.warning("Unknown universe '%s', defaulting to NIFTY50", universe)
    return list(NIFTY50)
