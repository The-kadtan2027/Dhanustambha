"""Historical signal backtesting utilities for scanner calibration."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

import config
from src.ingestion.store import get_ohlcv_range
from src.ingestion.symbols import get_universe_symbols
from src.scanner.episodic_pivot import detect_episodic_pivot
from src.scanner.momentum_burst import detect_momentum_burst
from src.scanner.trend_intensity import detect_trend_intensity


ScannerFn = Callable[..., pd.DataFrame]


@dataclass
class BacktestResult:
    """Summary plus signal-level output for one scanner/parameter run."""

    scanner_name: str
    universe: str
    start_date: str
    end_date: str
    params: Dict[str, object]
    n_signals: int
    signal_results: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)
    avg_return_5d: float = 0.0
    avg_return_10d: float = 0.0
    avg_return_20d: float = 0.0
    win_rate_5d: float = 0.0
    win_rate_10d: float = 0.0
    win_rate_20d: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        """Return a flat dictionary suitable for CSV output."""
        return {
            "scanner_name": self.scanner_name,
            "universe": self.universe,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "n_signals": self.n_signals,
            "avg_return_5d": self.avg_return_5d,
            "avg_return_10d": self.avg_return_10d,
            "avg_return_20d": self.avg_return_20d,
            "win_rate_5d": self.win_rate_5d,
            "win_rate_10d": self.win_rate_10d,
            "win_rate_20d": self.win_rate_20d,
            **self.params,
        }


def get_scanner(name: str) -> ScannerFn:
    """Resolve a scanner by CLI-friendly name."""
    scanners = {
        "momentum_burst": detect_momentum_burst,
        "episodic_pivot": detect_episodic_pivot,
        "trend_intensity": detect_trend_intensity,
    }
    scanner_name = name.strip().lower()
    if scanner_name not in scanners:
        raise ValueError(f"Unknown scanner '{name}'.")
    return scanners[scanner_name]


def run_backtest(
    scanner_fn: ScannerFn,
    universe: str,
    start_date: str,
    end_date: str,
    params: Optional[Dict[str, object]] = None,
    price_history: Optional[pd.DataFrame] = None,
    forward_days: Sequence[int] = config.BACKTEST_FORWARD_DAYS,
) -> BacktestResult:
    """Run a forward-return backtest for one scanner over historical data."""
    params = params or {}
    horizons = tuple(sorted(forward_days))

    if price_history is None:
        symbols = get_universe_symbols(universe)
        end_with_horizon = (
            pd.Timestamp(end_date) + pd.tseries.offsets.BDay(max(horizons))
        ).date().isoformat()
        price_history = get_ohlcv_range(start_date, end_with_horizon, symbols=symbols)
    else:
        price_history = price_history.copy()

    if price_history.empty:
        return BacktestResult(
            scanner_name=scanner_fn.__name__,
            universe=universe,
            start_date=start_date,
            end_date=end_date,
            params=params,
            n_signals=0,
        )

    price_history["date"] = pd.to_datetime(price_history["date"])
    price_history = price_history.sort_values(["symbol", "date"]).reset_index(drop=True)

    symbol_frames = {
        symbol: group.reset_index(drop=True)
        for symbol, group in price_history.groupby("symbol")
    }
    symbol_index_lookup = {
        symbol: {row_date: idx for idx, row_date in enumerate(group["date"])}
        for symbol, group in symbol_frames.items()
    }

    evaluation_dates = [
        trading_date
        for trading_date in sorted(price_history["date"].unique())
        if pd.Timestamp(start_date) <= trading_date <= pd.Timestamp(end_date)
    ]

    signal_rows: List[Dict[str, object]] = []
    for trading_date in evaluation_dates:
        history_slice = price_history[price_history["date"] <= trading_date]
        signals = scanner_fn(history_slice, **params)
        if signals.empty:
            continue

        for _, signal in signals.iterrows():
            symbol = str(signal["symbol"])
            if symbol not in symbol_frames:
                continue

            symbol_frame = symbol_frames[symbol]
            index_map = symbol_index_lookup[symbol]
            if trading_date not in index_map:
                continue

            current_idx = index_map[trading_date]
            entry_close = float(symbol_frame.iloc[current_idx]["close"])
            record: Dict[str, object] = {
                "date": trading_date.date().isoformat(),
                "symbol": symbol,
                "setup_type": signal.get("setup_type", scanner_fn.__name__.upper()),
                "entry_close": entry_close,
                "score": float(signal.get("score", 0.0)),
            }

            for horizon in horizons:
                future_idx = current_idx + horizon
                key = f"return_{horizon}d"
                if future_idx >= len(symbol_frame):
                    record[key] = None
                    continue

                future_close = float(symbol_frame.iloc[future_idx]["close"])
                record[key] = round((future_close - entry_close) / entry_close * 100, 2)

            signal_rows.append(record)

    signals_df = pd.DataFrame(signal_rows)
    result = BacktestResult(
        scanner_name=scanner_fn.__name__,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        params=params,
        n_signals=len(signals_df),
        signal_results=signals_df,
    )

    if signals_df.empty:
        return result

    for horizon in horizons:
        key = f"return_{horizon}d"
        series = signals_df[key].dropna()
        avg_value = round(float(series.mean()), 2) if not series.empty else 0.0
        win_rate = round(float((series > 0).mean() * 100), 1) if not series.empty else 0.0
        setattr(result, f"avg_return_{horizon}d", avg_value)
        setattr(result, f"win_rate_{horizon}d", win_rate)

    return result


def build_parameter_grid(scanner_name: str) -> List[Dict[str, object]]:
    """Return the parameter combinations for a scanner calibration run."""
    normalized = scanner_name.strip().lower()
    if normalized == "momentum_burst":
        keys = ["min_pct", "min_vol_ratio"]
        values = [(3.0, 5.0, 8.0), (1.2, 1.5, 2.0, 2.5)]
    elif normalized == "episodic_pivot":
        keys = ["min_gap_pct", "min_gap_vol_ratio"]
        values = [(3.0, 4.0, 6.0), (2.0, 3.0, 5.0)]
    elif normalized == "trend_intensity":
        keys = ["max_atr_pct", "min_days_above_ma50"]
        values = [(0.02, 0.03, 0.05), (20, 30, 40)]
    else:
        raise ValueError(f"Unknown scanner '{scanner_name}'.")

    return [dict(zip(keys, combo)) for combo in product(*values)]
