"""Watchlist merging, ranking, and export helpers."""

import logging
import os
from datetime import date
from typing import List, Optional

import pandas as pd

import config
from src.ingestion.store import save_watchlist


logger = logging.getLogger(__name__)


def merge_and_rank(
    results: List[pd.DataFrame], scan_date: Optional[str] = None
) -> pd.DataFrame:
    """Merge scanner outputs, deduplicate symbols, and rank by score."""
    if scan_date is None:
        scan_date = date.today().isoformat()

    non_empty_results = [result for result in results if not result.empty]
    if not non_empty_results:
        return pd.DataFrame()

    all_results = pd.concat(non_empty_results, ignore_index=True)
    all_results["date"] = scan_date

    ranked = (
        all_results.sort_values("score", ascending=False)
        .drop_duplicates(subset="symbol", keep="first")
        .reset_index(drop=True)
    )
    return ranked.head(config.MAX_WATCHLIST_SIZE)


def export_watchlist(df: pd.DataFrame, scan_date: Optional[str] = None) -> str:
    """Export a watchlist DataFrame to CSV and SQLite, returning the CSV path."""
    if scan_date is None:
        scan_date = date.today().isoformat()

    os.makedirs(config.WATCHLIST_DIR, exist_ok=True)
    csv_path = os.path.join(config.WATCHLIST_DIR, f"{scan_date}.csv")
    df.to_csv(csv_path, index=False)
    logger.info("Watchlist saved to %s", csv_path)

    save_watchlist(df.to_dict(orient="records"))
    return csv_path
