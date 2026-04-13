"""SQLite storage helpers for market data and scan results."""

import logging
import sqlite3
from typing import Dict, List, Optional

import pandas as pd

import config


logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection to the configured database path."""
    return sqlite3.connect(config.DB_PATH)


def init_db() -> None:
    """Create all Phase 1 tables and indexes if they do not already exist."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executescript(
            """
            CREATE TABLE IF NOT EXISTS symbols (
                symbol      TEXT PRIMARY KEY,
                name        TEXT,
                sector      TEXT,
                index_name  TEXT,
                active      INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS ohlcv (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT NOT NULL,
                date        TEXT NOT NULL,
                open        REAL,
                high        REAL,
                low         REAL,
                close       REAL,
                volume      INTEGER,
                UNIQUE(symbol, date),
                FOREIGN KEY (symbol) REFERENCES symbols(symbol)
            );

            CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_date
            ON ohlcv(symbol, date);

            CREATE INDEX IF NOT EXISTS idx_ohlcv_date
            ON ohlcv(date);

            CREATE TABLE IF NOT EXISTS breadth (
                date                TEXT PRIMARY KEY,
                pct_above_ma20      REAL,
                pct_above_ma50      REAL,
                new_highs_52w       INTEGER,
                new_lows_52w        INTEGER,
                up_volume_ratio     REAL,
                advancing           INTEGER,
                declining           INTEGER,
                verdict             TEXT
            );

            CREATE TABLE IF NOT EXISTS watchlist (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT NOT NULL,
                symbol          TEXT NOT NULL,
                setup_type      TEXT NOT NULL,
                score           REAL,
                pct_change      REAL,
                volume_ratio    REAL,
                close           REAL,
                notes           TEXT
            );
            """
        )
        conn.commit()
        logger.info("Database initialized at %s", config.DB_PATH)
    except sqlite3.OperationalError as exc:
        logger.error("Failed to initialize database: %s", exc)
        raise
    finally:
        conn.close()


def upsert_ohlcv(rows: List[Dict]) -> int:
    """Insert or replace OHLCV rows and return the number of processed rows."""
    if not rows:
        return 0

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT OR REPLACE INTO ohlcv
                (symbol, date, open, high, low, close, volume)
            VALUES
                (:symbol, :date, :open, :high, :low, :close, :volume)
            """,
            rows,
        )
        conn.commit()
        logger.debug("Upserted %d OHLCV rows", len(rows))
        return len(rows)
    except sqlite3.OperationalError as exc:
        logger.error("Failed to upsert OHLCV rows: %s", exc)
        raise
    finally:
        conn.close()


def get_ohlcv(symbol: str, days: int = 252) -> pd.DataFrame:
    """Return recent OHLCV history for one symbol as a date-sorted DataFrame."""
    conn = get_connection()
    try:
        df = pd.read_sql(
            """
            SELECT date, open, high, low, close, volume
            FROM ohlcv
            WHERE symbol = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            conn,
            params=(symbol, days),
        )
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except sqlite3.OperationalError as exc:
        logger.error("Failed to fetch OHLCV for %s: %s", symbol, exc)
        raise
    finally:
        conn.close()


def get_all_symbols_ohlcv(date: str, lookback_days: int = 252) -> pd.DataFrame:
    """Return OHLCV data for all symbols up to a given date."""
    conn = get_connection()
    try:
        df = pd.read_sql(
            """
            SELECT symbol, date, open, high, low, close, volume
            FROM ohlcv
            WHERE date <= ?
            ORDER BY symbol, date
            """,
            conn,
            params=(date,),
        )
        df["date"] = pd.to_datetime(df["date"])
        return df
    except sqlite3.OperationalError as exc:
        logger.error("Failed to fetch all symbols OHLCV for %s: %s", date, exc)
        raise
    finally:
        conn.close()


def get_stored_dates(
    start_date: Optional[str] = None, end_date: Optional[str] = None
) -> List[str]:
    """Return sorted distinct OHLCV dates already stored in the database."""
    conn = get_connection()
    try:
        query = ["SELECT DISTINCT date FROM ohlcv WHERE 1 = 1"]
        params: List[str] = []

        if start_date is not None:
            query.append("AND date >= ?")
            params.append(start_date)

        if end_date is not None:
            query.append("AND date <= ?")
            params.append(end_date)

        query.append("ORDER BY date")
        rows = conn.execute(" ".join(query), tuple(params)).fetchall()
        return [row[0] for row in rows]
    except sqlite3.OperationalError as exc:
        logger.error("Failed to fetch stored dates: %s", exc)
        raise
    finally:
        conn.close()


def save_breadth(record: Dict) -> None:
    """Insert or replace a breadth record for one trading day."""
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO breadth
                (
                    date,
                    pct_above_ma20,
                    pct_above_ma50,
                    new_highs_52w,
                    new_lows_52w,
                    up_volume_ratio,
                    advancing,
                    declining,
                    verdict
                )
            VALUES
                (
                    :date,
                    :pct_above_ma20,
                    :pct_above_ma50,
                    :new_highs_52w,
                    :new_lows_52w,
                    :up_volume_ratio,
                    :advancing,
                    :declining,
                    :verdict
                )
            """,
            record,
        )
        conn.commit()
        logger.info("Saved breadth for %s: %s", record["date"], record["verdict"])
    except sqlite3.OperationalError as exc:
        logger.error("Failed to save breadth for %s: %s", record.get("date"), exc)
        raise
    finally:
        conn.close()


def save_watchlist(entries: List[Dict]) -> None:
    """Insert watchlist entries for a single scan day."""
    if not entries:
        return

    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO watchlist
                (date, symbol, setup_type, score, pct_change, volume_ratio, close, notes)
            VALUES
                (:date, :symbol, :setup_type, :score, :pct_change, :volume_ratio, :close, :notes)
            """,
            entries,
        )
        conn.commit()
        logger.info("Saved %d watchlist entries", len(entries))
    except sqlite3.OperationalError as exc:
        logger.error("Failed to save watchlist: %s", exc)
        raise
    finally:
        conn.close()
