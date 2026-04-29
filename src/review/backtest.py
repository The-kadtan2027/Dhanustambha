"""Historical signal backtesting utilities for scanner calibration."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
import json
from typing import Callable, Dict, Iterable, List, Optional, Sequence

import pandas as pd

import config
from src.ingestion.store import get_breadth_range, get_ohlcv_range
from src.ingestion.symbols import get_universe_symbols
from src.scanner.episodic_pivot import detect_episodic_pivot, prepare_episodic_pivot_features
from src.scanner.momentum_burst import detect_momentum_burst, prepare_momentum_burst_features
from src.scanner.trend_intensity import detect_trend_intensity, prepare_trend_intensity_features


ScannerFn = Callable[..., pd.DataFrame]


@dataclass
class BacktestResult:
    """Summary plus signal-level output for one scanner/parameter run."""

    scanner_name: str
    universe: str
    start_date: str
    end_date: str
    params: Dict[str, object]
    param_set_id: str
    n_signals: int
    signal_results: pd.DataFrame = field(default_factory=pd.DataFrame, repr=False)
    summary_metrics: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        """Return a flat dictionary suitable for CSV output."""
        result = {
            "scanner_name": self.scanner_name,
            "universe": self.universe,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "param_set_id": self.param_set_id,
            "n_signals": self.n_signals,
            **self.params,
        }
        result.update(self.summary_metrics)
        return result


def _build_param_set_id(scanner_name: str, params: Dict[str, object]) -> str:
    """Return a stable identifier for one scanner parameter set."""
    if not params:
        return f"{scanner_name}:default"
    serialized = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return f"{scanner_name}:{serialized}"


def _normalize_horizons(defaults: Sequence[int], extras: Iterable[int]) -> tuple[int, ...]:
    """Return sorted unique horizons used across summary and signal metrics."""
    return tuple(sorted(set(defaults) | set(extras)))


def _select_benchmark_history(benchmark_history: pd.DataFrame) -> pd.DataFrame:
    """Return one benchmark series from the provided benchmark history DataFrame."""
    if benchmark_history.empty:
        return benchmark_history

    if "symbol" not in benchmark_history.columns:
        return benchmark_history.sort_values("date").reset_index(drop=True)

    unique_symbols = [str(symbol) for symbol in benchmark_history["symbol"].dropna().unique()]
    for candidate in config.BACKTEST_BENCHMARK_CANDIDATES:
        if candidate in unique_symbols:
            return (
                benchmark_history[benchmark_history["symbol"] == candidate]
                .sort_values("date")
                .reset_index(drop=True)
            )

    if len(unique_symbols) == 1:
        return benchmark_history.sort_values("date").reset_index(drop=True)

    return pd.DataFrame(columns=benchmark_history.columns)


def _build_local_benchmark_proxy(price_history: pd.DataFrame) -> pd.DataFrame:
    """Build an equal-weight benchmark proxy from the locally available universe history.

    When no external benchmark series is available in the local OHLCV store, we approximate
    the benchmark as an equal-weight index of the available symbol universe. This keeps the
    calibration workflow alpha-aware within the repo's local data constraints.
    """
    if price_history.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    working = price_history.copy()
    working["date"] = pd.to_datetime(working["date"])
    benchmark_symbols = set(config.BACKTEST_BENCHMARK_CANDIDATES)
    working = working[~working["symbol"].astype(str).isin(benchmark_symbols)]
    if working.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    working = working.sort_values(["symbol", "date"]).reset_index(drop=True)
    working["prev_close"] = working.groupby("symbol")["close"].shift(1)
    working["daily_return"] = working["close"] / working["prev_close"] - 1.0

    grouped = (
        working.dropna(subset=["daily_return"])
        .groupby("date")
        .agg(
            benchmark_return=("daily_return", "mean"),
            total_volume=("volume", "sum"),
        )
        .reset_index()
        .sort_values("date")
        .reset_index(drop=True)
    )
    if grouped.empty:
        return pd.DataFrame(columns=["symbol", "date", "open", "high", "low", "close", "volume"])

    benchmark_close = [100.0]
    for daily_return in grouped["benchmark_return"].iloc[1:]:
        benchmark_close.append(round(benchmark_close[-1] * (1.0 + float(daily_return)), 6))

    grouped["close"] = benchmark_close
    grouped["open"] = grouped["close"].shift(1).fillna(grouped["close"])
    grouped["high"] = grouped[["open", "close"]].max(axis=1)
    grouped["low"] = grouped[["open", "close"]].min(axis=1)
    grouped["volume"] = grouped["total_volume"].fillna(0).astype(int)
    grouped["symbol"] = config.BACKTEST_BENCHMARK_SYMBOL
    return grouped[["symbol", "date", "open", "high", "low", "close", "volume"]]


def _build_index_lookup(frame: pd.DataFrame) -> Dict[pd.Timestamp, int]:
    """Return a mapping from trading date to row index for one OHLCV series."""
    return {row_date: idx for idx, row_date in enumerate(frame["date"])}


def _compute_forward_return(
    frame: pd.DataFrame,
    current_idx: int,
    horizon: int,
    entry_close: float,
) -> Optional[float]:
    """Return the percentage forward close-to-close return for one horizon."""
    future_idx = current_idx + horizon
    if future_idx >= len(frame):
        return None

    future_close = float(frame.iloc[future_idx]["close"])
    return round((future_close - entry_close) / entry_close * 100, 2)


def _compute_excursion_metrics(
    frame: pd.DataFrame,
    current_idx: int,
    horizon: int,
    entry_close: float,
) -> tuple[Optional[float], Optional[float]]:
    """Return MFE and MAE percentages over the forward window for one horizon."""
    future_idx = current_idx + horizon
    if future_idx >= len(frame):
        return None, None

    future_window = frame.iloc[current_idx + 1 : future_idx + 1]
    if future_window.empty:
        return None, None

    max_high = float(future_window["high"].max())
    min_low = float(future_window["low"].min())
    mfe = round((max_high - entry_close) / entry_close * 100, 2)
    mae = round((min_low - entry_close) / entry_close * 100, 2)
    return mfe, mae


def _compute_summary_metrics(
    signals_df: pd.DataFrame,
    horizons: Sequence[int],
    excursion_horizons: Sequence[int],
) -> Dict[str, object]:
    """Return aggregate summary metrics for one set of historical signals."""
    summary: Dict[str, object] = {}

    for horizon in horizons:
        return_key = f"return_{horizon}d"
        alpha_key = f"alpha_{horizon}d"
        return_series = signals_df[return_key].dropna() if return_key in signals_df else pd.Series(
            dtype=float
        )
        alpha_series = signals_df[alpha_key].dropna() if alpha_key in signals_df else pd.Series(
            dtype=float
        )

        summary[f"avg_return_{horizon}d"] = (
            round(float(return_series.mean()), 2) if not return_series.empty else 0.0
        )
        summary[f"median_return_{horizon}d"] = (
            round(float(return_series.median()), 2) if not return_series.empty else 0.0
        )
        summary[f"win_rate_{horizon}d"] = (
            round(float((return_series > 0).mean() * 100), 1) if not return_series.empty else 0.0
        )
        summary[f"avg_alpha_{horizon}d"] = (
            round(float(alpha_series.mean()), 2) if not alpha_series.empty else 0.0
        )
        summary[f"median_alpha_{horizon}d"] = (
            round(float(alpha_series.median()), 2) if not alpha_series.empty else 0.0
        )
        summary[f"alpha_win_rate_{horizon}d"] = (
            round(float((alpha_series > 0).mean() * 100), 1) if not alpha_series.empty else 0.0
        )

    for horizon in excursion_horizons:
        mfe_key = f"mfe_{horizon}d"
        mae_key = f"mae_{horizon}d"
        mfe_series = signals_df[mfe_key].dropna() if mfe_key in signals_df else pd.Series(dtype=float)
        mae_series = signals_df[mae_key].dropna() if mae_key in signals_df else pd.Series(dtype=float)
        summary[f"avg_mfe_{horizon}d"] = (
            round(float(mfe_series.mean()), 2) if not mfe_series.empty else 0.0
        )
        summary[f"avg_mae_{horizon}d"] = (
            round(float(mae_series.mean()), 2) if not mae_series.empty else 0.0
        )

    bool_columns = [
        "failed_to_gain_by_3d",
        "failed_to_gain_by_5d",
        "hit_2pct_by_3d",
        "hit_5pct_by_5d",
        "hit_8pct_by_10d",
    ]
    for column in bool_columns:
        series = signals_df[column].dropna() if column in signals_df else pd.Series(dtype=bool)
        summary[f"pct_{column}"] = round(float(series.mean() * 100), 1) if not series.empty else 0.0

    if "market_verdict" in signals_df.columns:
        for verdict in ("OFFENSIVE", "DEFENSIVE", "AVOID"):
            verdict_slice = signals_df[signals_df["market_verdict"] == verdict]
            summary[f"signals_{verdict.lower()}"] = int(len(verdict_slice))
            return_series = verdict_slice["return_5d"].dropna() if "return_5d" in verdict_slice else pd.Series(dtype=float)
            alpha_series = verdict_slice["alpha_5d"].dropna() if "alpha_5d" in verdict_slice else pd.Series(dtype=float)
            summary[f"{verdict.lower()}_win_rate_5d"] = (
                round(float((return_series > 0).mean() * 100), 1) if not return_series.empty else 0.0
            )
            summary[f"{verdict.lower()}_avg_alpha_5d"] = (
                round(float(alpha_series.mean()), 2) if not alpha_series.empty else 0.0
            )

    return summary


def _prepare_scanner_history(
    scanner_fn: ScannerFn,
    price_history: pd.DataFrame,
) -> object:
    """Precompute reusable scanner history structures for calibration runs."""
    if scanner_fn is detect_momentum_burst:
        prepared = prepare_momentum_burst_features(price_history)
        if prepared.empty:
            return {}
        return {
            trading_date: group.reset_index(drop=True)
            for trading_date, group in prepared.groupby("date")
        }
    if scanner_fn is detect_episodic_pivot:
        prepared = prepare_episodic_pivot_features(price_history)
        return prepared.reset_index(drop=True)
    if scanner_fn is detect_trend_intensity:
        prepared = prepare_trend_intensity_features(price_history)
        if prepared.empty:
            return {}
        return {
            trading_date: group.reset_index(drop=True)
            for trading_date, group in prepared.groupby("date")
        }
    return {}


def prepare_scanner_history(
    scanner_fn: ScannerFn,
    price_history: pd.DataFrame,
) -> object:
    """Return reusable precomputed scanner history for calibration runs."""
    return _prepare_scanner_history(scanner_fn, price_history)


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
    benchmark_history: Optional[pd.DataFrame] = None,
    breadth_history: Optional[pd.DataFrame] = None,
    prepared_history_by_date: Optional[object] = None,
    forward_days: Sequence[int] = config.BACKTEST_FORWARD_DAYS,
) -> BacktestResult:
    """Run a historical signal backtest with forward returns and benchmark-relative metrics."""
    params = params or {}
    horizons = _normalize_horizons(forward_days, config.BACKTEST_SIGNAL_HORIZONS)
    excursion_horizons = tuple(sorted(config.BACKTEST_EXCURSION_HORIZONS))
    param_set_id = _build_param_set_id(scanner_fn.__name__, params)

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
            param_set_id=param_set_id,
            n_signals=0,
        )

    price_history["date"] = pd.to_datetime(price_history["date"])
    price_history = price_history.sort_values(["symbol", "date"]).reset_index(drop=True)
    if prepared_history_by_date is None:
        prepared_history_by_date = _prepare_scanner_history(scanner_fn, price_history)

    symbol_frames = {
        symbol: group.reset_index(drop=True)
        for symbol, group in price_history.groupby("symbol")
    }
    symbol_index_lookup = {symbol: _build_index_lookup(group) for symbol, group in symbol_frames.items()}

    if benchmark_history is None:
        end_with_horizon = (
            pd.Timestamp(end_date) + pd.tseries.offsets.BDay(max(horizons))
        ).date().isoformat()
        benchmark_history = get_ohlcv_range(
            start_date,
            end_with_horizon,
            symbols=config.BACKTEST_BENCHMARK_CANDIDATES,
        )
    else:
        benchmark_history = benchmark_history.copy()

    benchmark_frame = pd.DataFrame()
    benchmark_index_lookup: Dict[pd.Timestamp, int] = {}
    if not benchmark_history.empty:
        benchmark_history["date"] = pd.to_datetime(benchmark_history["date"])
        benchmark_frame = _select_benchmark_history(benchmark_history)
    if benchmark_frame.empty:
        benchmark_frame = _build_local_benchmark_proxy(price_history)
    if not benchmark_frame.empty:
        benchmark_frame["date"] = pd.to_datetime(benchmark_frame["date"])
        benchmark_frame = benchmark_frame.sort_values("date").reset_index(drop=True)
        benchmark_index_lookup = _build_index_lookup(benchmark_frame)

    if breadth_history is None:
        breadth_history = get_breadth_range(start_date, end_date)
    else:
        breadth_history = breadth_history.copy()

    breadth_lookup: Dict[str, Dict[str, object]] = {}
    if not breadth_history.empty:
        breadth_history["date"] = pd.to_datetime(breadth_history["date"])
        breadth_lookup = {
            row["date"].date().isoformat(): {
                "market_verdict": row.get("verdict"),
                "pct_above_ma20_on_day": row.get("pct_above_ma20"),
                "pct_above_ma50_on_day": row.get("pct_above_ma50"),
                "new_highs_52w_on_day": row.get("new_highs_52w"),
                "new_lows_52w_on_day": row.get("new_lows_52w"),
                "up_volume_ratio_on_day": row.get("up_volume_ratio"),
                "advancing_on_day": row.get("advancing"),
                "declining_on_day": row.get("declining"),
            }
            for _, row in breadth_history.iterrows()
        }

    evaluation_dates = [
        trading_date
        for trading_date in sorted(price_history["date"].unique())
        if pd.Timestamp(start_date) <= trading_date <= pd.Timestamp(end_date)
    ]

    signal_rows: List[Dict[str, object]] = []
    for trading_date in evaluation_dates:
        if isinstance(prepared_history_by_date, dict) and prepared_history_by_date:
            history_slice = prepared_history_by_date.get(trading_date, pd.DataFrame())
            signals = scanner_fn(history_slice, **params) if not history_slice.empty else pd.DataFrame()
        elif isinstance(prepared_history_by_date, pd.DataFrame) and not prepared_history_by_date.empty:
            history_slice = prepared_history_by_date[
                prepared_history_by_date["date"] <= trading_date
            ]
            signals = scanner_fn(history_slice, **params)
        else:
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
                "scanner_name": scanner_fn.__name__,
                "param_set_id": param_set_id,
            }
            for column, value in signal.items():
                if column == "symbol":
                    continue
                if isinstance(value, pd.Timestamp):
                    record[column] = value.date().isoformat()
                else:
                    record[column] = value

            record.update(
                breadth_lookup.get(
                    trading_date.date().isoformat(),
                    {
                        "market_verdict": None,
                        "pct_above_ma20_on_day": None,
                        "pct_above_ma50_on_day": None,
                        "new_highs_52w_on_day": None,
                        "new_lows_52w_on_day": None,
                        "up_volume_ratio_on_day": None,
                        "advancing_on_day": None,
                        "declining_on_day": None,
                    },
                )
            )

            benchmark_idx = benchmark_index_lookup.get(trading_date)
            benchmark_entry_close: Optional[float] = None
            if benchmark_idx is not None and not benchmark_frame.empty:
                benchmark_entry_close = float(benchmark_frame.iloc[benchmark_idx]["close"])

            for horizon in horizons:
                return_key = f"return_{horizon}d"
                benchmark_key = f"nifty_return_{horizon}d"
                alpha_key = f"alpha_{horizon}d"
                record[return_key] = _compute_forward_return(
                    symbol_frame,
                    current_idx,
                    horizon,
                    entry_close,
                )
                if benchmark_entry_close is None or benchmark_idx is None:
                    record[benchmark_key] = None
                    record[alpha_key] = None
                else:
                    benchmark_return = _compute_forward_return(
                        benchmark_frame,
                        benchmark_idx,
                        horizon,
                        benchmark_entry_close,
                    )
                    record[benchmark_key] = benchmark_return
                    record[alpha_key] = (
                        round(record[return_key] - benchmark_return, 2)
                        if record[return_key] is not None and benchmark_return is not None
                        else None
                    )

            for horizon in excursion_horizons:
                mfe, mae = _compute_excursion_metrics(
                    symbol_frame,
                    current_idx,
                    horizon,
                    entry_close,
                )
                record[f"mfe_{horizon}d"] = mfe
                record[f"mae_{horizon}d"] = mae

            record["failed_to_gain_by_3d"] = (
                record["mfe_3d"] is not None and record["mfe_3d"] <= 0
            )
            record["failed_to_gain_by_5d"] = (
                record["mfe_5d"] is not None and record["mfe_5d"] <= 0
            )
            record["hit_2pct_by_3d"] = (
                record["mfe_3d"] is not None and record["mfe_3d"] >= 2.0
            )
            record["hit_5pct_by_5d"] = (
                record["mfe_5d"] is not None and record["mfe_5d"] >= 5.0
            )
            record["hit_8pct_by_10d"] = (
                record["mfe_10d"] is not None and record["mfe_10d"] >= 8.0
            )

            signal_rows.append(record)

    signals_df = pd.DataFrame(signal_rows)
    result = BacktestResult(
        scanner_name=scanner_fn.__name__,
        universe=universe,
        start_date=start_date,
        end_date=end_date,
        params=params,
        param_set_id=param_set_id,
        n_signals=len(signals_df),
        signal_results=signals_df,
    )

    if signals_df.empty:
        return result

    result.summary_metrics = _compute_summary_metrics(signals_df, horizons, excursion_horizons)
    for key, value in result.summary_metrics.items():
        setattr(result, key, value)

    return result


def build_parameter_grid(scanner_name: str) -> List[Dict[str, object]]:
    """Return the parameter combinations for a scanner calibration run."""
    normalized = scanner_name.strip().lower()
    if normalized == "momentum_burst":
        keys = ["min_pct", "min_vol_ratio", "max_prior_run"]
        values = [
            (4.0, 5.0, 6.0, 7.0, 8.0),
            (1.3, 1.5, 1.8, 2.0, 2.5),
            (8.0, 10.0, 12.0, 15.0),
        ]
    elif normalized == "episodic_pivot":
        keys = ["min_gap_pct", "min_gap_vol_ratio", "max_days_since_gap"]
        values = [
            (4.0, 5.0, 6.0, 8.0),
            (3.0, 4.0, 5.0, 6.0),
            (1, 2, 3, 5),
        ]
    elif normalized == "trend_intensity":
        keys = ["max_atr_pct", "min_days_above_ma50", "min_vol_ratio"]
        values = [
            (0.02, 0.03, 0.04, 0.05),
            (30, 35, 40, 45),
            (1.2, 1.3, 1.5),
        ]
    else:
        raise ValueError(f"Unknown scanner '{scanner_name}'.")

    return [dict(zip(keys, combo)) for combo in product(*values)]
