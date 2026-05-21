"""Watchlist merging, ranking, and export helpers."""

import logging
import os
from datetime import date
from typing import List, Optional

import pandas as pd

import config
from src.ingestion.store import clear_watchlist, save_watchlist


logger = logging.getLogger(__name__)
WATCHLIST_DB_COLUMNS = [
    "date",
    "symbol",
    "setup_type",
    "score",
    "pct_change",
    "volume_ratio",
    "close",
    "notes",
]


def merge_and_rank(
    results: List[pd.DataFrame], scan_date: Optional[str] = None
) -> pd.DataFrame:
    """Merge scanner outputs, preserve multi-setup matches, and rank by score."""
    if scan_date is None:
        scan_date = date.today().isoformat()

    non_empty_results = [
        result.sort_values("score", ascending=False).reset_index(drop=True)
        for result in results if not result.empty
    ]
    if not non_empty_results:
        return pd.DataFrame()

    interleaved = []
    max_len = max(len(r) for r in non_empty_results)
    for i in range(max_len):
        for r in non_empty_results:
            if i < len(r):
                interleaved.append(r.iloc[i : i + 1])

    all_results = pd.concat(interleaved, ignore_index=True)
    all_results["date"] = scan_date
    all_results["matched_setups"] = (
        all_results.groupby("symbol")["setup_type"]
        .transform(
            lambda values: ", ".join(
                dict.fromkeys(
                    str(value) for value in values if pd.notna(value)
                )
            )
        )
    )
    all_results["setup_match_count"] = (
        all_results["matched_setups"].str.count(",") + 1
    )

    ranked = (
        all_results.drop_duplicates(subset="symbol", keep="first")
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

    db_df = df[[column for column in WATCHLIST_DB_COLUMNS if column in df.columns]].copy()
    if db_df.empty:
        clear_watchlist(scan_date)
    else:
        save_watchlist(db_df.to_dict(orient="records"))
    return csv_path
