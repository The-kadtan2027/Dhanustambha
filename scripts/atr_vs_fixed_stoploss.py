"""Head-to-head: ATR-based stops vs Fixed % stops.

Loads historical signal data, computes ATR(14) for each signal from the
OHLCV database, then simulates both stop-loss approaches side-by-side
to determine which produces better expectancy.

Focus: Episodic Pivot (proven alpha scanner) and Momentum Burst.
"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import time

import config
from src.ingestion.store import get_ohlcv_range


def compute_atr_for_signals(signals_df: pd.DataFrame) -> pd.DataFrame:
    """Join ATR(14) from OHLCV history to each signal row."""
    print("  Computing ATR(14) for each signal from OHLCV database...")
    start = time.time()

    # Get unique symbols and date range
    symbols = signals_df["symbol"].unique().tolist()
    min_date = pd.to_datetime(signals_df["date"]).min()
    # Need 14+ prior days for ATR calculation
    lookback_start = (min_date - pd.tseries.offsets.BDay(30)).date().isoformat()
    max_date = pd.to_datetime(signals_df["date"]).max().date().isoformat()

    print(f"    Fetching OHLCV for {len(symbols)} symbols, {lookback_start} to {max_date}...")
    ohlcv = get_ohlcv_range(lookback_start, max_date, symbols=symbols)
    if ohlcv.empty:
        print("    WARNING: No OHLCV data found!")
        signals_df["atr_14"] = np.nan
        signals_df["atr_pct"] = np.nan
        return signals_df

    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    ohlcv = ohlcv.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Compute ATR(14) per symbol
    def _calc_atr(group: pd.DataFrame) -> pd.DataFrame:
        """Compute ATR(14) for one symbol's history."""
        group = group.sort_values("date").copy()
        group["prev_close"] = group["close"].shift(1)
        group["tr"] = np.maximum(
            group["high"] - group["low"],
            np.maximum(
                (group["high"] - group["prev_close"]).abs(),
                (group["low"] - group["prev_close"]).abs()
            )
        )
        group["atr_14"] = group["tr"].rolling(window=14, min_periods=14).mean()
        group["atr_pct"] = (group["atr_14"] / group["close"]) * 100
        return group[["symbol", "date", "atr_14", "atr_pct"]]

    atr_data = ohlcv.groupby("symbol", group_keys=False).apply(_calc_atr)
    atr_data = atr_data.dropna(subset=["atr_14"])

    # Create a merge key
    signals_df["date_dt"] = pd.to_datetime(signals_df["date"])
    atr_data["date_dt"] = atr_data["date"]

    # Merge ATR onto signals
    result = signals_df.merge(
        atr_data[["symbol", "date_dt", "atr_14", "atr_pct"]],
        on=["symbol", "date_dt"],
        how="left"
    )
    result.drop(columns=["date_dt"], inplace=True)

    valid_atr = result["atr_14"].notna().sum()
    elapsed = time.time() - start
    print(f"    ATR joined: {valid_atr}/{len(result)} signals have ATR ({elapsed:.1f}s)")
    print(f"    ATR% distribution: P25={result['atr_pct'].quantile(0.25):.2f}%, "
          f"P50={result['atr_pct'].quantile(0.50):.2f}%, "
          f"P75={result['atr_pct'].quantile(0.75):.2f}%")

    return result


def simulate_stop(signals_df: pd.DataFrame, stop_col: str, horizon: str = "5d") -> dict:
    """Simulate a stop-loss strategy using a pre-computed stop distance column.

    stop_col: column name containing the stop distance as a % (e.g. 'fixed_stop_2.5' or 'atr_stop_2.0x')
    """
    mae_col = f"mae_{horizon}"
    mfe_col = f"mfe_{horizon}"
    return_col = f"return_{horizon}"

    valid = signals_df.dropna(subset=[mae_col, mfe_col, return_col, stop_col]).copy()
    if valid.empty:
        return {"stop_method": stop_col, "n": 0, "expectancy": 0}

    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["is_winner"] = valid[return_col] > 0
    valid["sl_pct"] = valid[stop_col]

    # For each trade: was it stopped out?
    valid["stopped_out"] = valid["drawdown_pct"] > valid["sl_pct"]

    # R-multiple calculation
    # Stopped out (winner or loser): lose 1R
    # Not stopped, winner: gain = return / sl_pct (in R)
    # Not stopped, loser: lose = |return| / sl_pct (in R, negative)
    r_values = []
    for _, row in valid.iterrows():
        sl = row["sl_pct"]
        if sl <= 0:
            continue
        if row["stopped_out"]:
            r_values.append(-1.0)
        else:
            r_values.append(row[return_col] / sl)

    if not r_values:
        return {"stop_method": stop_col, "n": 0, "expectancy": 0}

    r_arr = np.array(r_values)
    win_count = np.sum(r_arr > 0)
    loss_count = np.sum(r_arr <= 0)
    total = len(r_arr)
    win_rate = win_count / total * 100

    avg_win = float(np.mean(r_arr[r_arr > 0])) if win_count > 0 else 0
    avg_loss = float(np.mean(np.abs(r_arr[r_arr <= 0]))) if loss_count > 0 else 0
    expectancy = (win_rate / 100 * avg_win) - ((100 - win_rate) / 100 * avg_loss)
    avg_r = float(np.mean(r_arr))

    # Winners kept vs stopped
    winner_mask = valid["is_winner"]
    winners_stopped = int((winner_mask & valid["stopped_out"]).sum())
    winners_kept = int((winner_mask & ~valid["stopped_out"]).sum())
    losers_stopped = int((~winner_mask & valid["stopped_out"]).sum())

    # Average stop distance used
    avg_stop = float(valid["sl_pct"].mean())
    median_stop = float(valid["sl_pct"].median())

    return {
        "stop_method": stop_col,
        "n": total,
        "win_rate": round(win_rate, 1),
        "avg_r": round(avg_r, 4),
        "expectancy": round(expectancy, 4),
        "avg_win_r": round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "winners_kept": winners_kept,
        "winners_stopped": winners_stopped,
        "losers_stopped": losers_stopped,
        "avg_stop_pct": round(avg_stop, 2),
        "median_stop_pct": round(median_stop, 2),
    }


def run_comparison(signals_df: pd.DataFrame, scanner_name: str, horizon: str = "5d"):
    """Run head-to-head comparison of fixed vs ATR stops."""
    print(f"\n{'='*75}")
    print(f"  {scanner_name} -- {horizon} horizon -- FIXED % vs ATR STOPS")
    print(f"{'='*75}")

    # --- Create stop columns ---
    # Fixed % stops
    for pct in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
        signals_df[f"fixed_{pct}"] = pct

    # ATR-based stops (N x ATR as a % of entry price)
    for mult in [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
        signals_df[f"atr_{mult}x"] = signals_df["atr_pct"] * mult

    # --- Simulate all ---
    results = []

    print(f"\n  {'Method':<18s} | {'WinRate':>7s} | {'Expect':>8s} | {'AvgR':>7s} | "
          f"{'AvgWin':>6s} | {'AvgLoss':>7s} | {'WKept':>6s} | {'WStopped':>8s} | "
          f"{'LStopped':>8s} | {'AvgSL%':>6s} | {'MedSL%':>6s}")
    print(f"  {'-'*18} | {'-'*7} | {'-'*8} | {'-'*7} | {'-'*6} | {'-'*7} | "
          f"{'-'*6} | {'-'*8} | {'-'*8} | {'-'*6} | {'-'*6}")

    # Fixed stops
    for pct in [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0]:
        r = simulate_stop(signals_df, f"fixed_{pct}", horizon)
        results.append(r)
        if r["n"] > 0:
            print(f"  Fixed {pct:4.1f}%       | {r['win_rate']:6.1f}% | {r['expectancy']:+7.4f}R | "
                  f"{r['avg_r']:+6.4f}R | {r['avg_win_r']:+5.2f}R | {r['avg_loss_r']:5.2f}R | "
                  f"{r['winners_kept']:5d} | {r['winners_stopped']:7d} | "
                  f"{r['losers_stopped']:7d} | {r['avg_stop_pct']:5.2f}% | {r['median_stop_pct']:5.2f}%")

    print(f"  {'-'*18} | {'-'*7} | {'-'*8} | {'-'*7} | {'-'*6} | {'-'*7} | "
          f"{'-'*6} | {'-'*8} | {'-'*8} | {'-'*6} | {'-'*6}")

    # ATR stops
    for mult in [0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]:
        r = simulate_stop(signals_df, f"atr_{mult}x", horizon)
        results.append(r)
        if r["n"] > 0:
            print(f"  ATR x{mult:<4.2f}        | {r['win_rate']:6.1f}% | {r['expectancy']:+7.4f}R | "
                  f"{r['avg_r']:+6.4f}R | {r['avg_win_r']:+5.2f}R | {r['avg_loss_r']:5.2f}R | "
                  f"{r['winners_kept']:5d} | {r['winners_stopped']:7d} | "
                  f"{r['losers_stopped']:7d} | {r['avg_stop_pct']:5.2f}% | {r['median_stop_pct']:5.2f}%")

    # --- Find best ---
    valid_results = [r for r in results if r["n"] > 0]
    if valid_results:
        best_fixed = max([r for r in valid_results if r["stop_method"].startswith("fixed")],
                         key=lambda x: x["expectancy"])
        best_atr = max([r for r in valid_results if r["stop_method"].startswith("atr")],
                       key=lambda x: x["expectancy"])
        overall_best = max(valid_results, key=lambda x: x["expectancy"])

        print(f"\n  BEST FIXED: {best_fixed['stop_method']} "
              f"(Expectancy: {best_fixed['expectancy']:+.4f}R, "
              f"WR: {best_fixed['win_rate']:.1f}%)")
        print(f"  BEST ATR:   {best_atr['stop_method']} "
              f"(Expectancy: {best_atr['expectancy']:+.4f}R, "
              f"WR: {best_atr['win_rate']:.1f}%, "
              f"Median SL: {best_atr['median_stop_pct']:.2f}%)")

        delta = best_atr["expectancy"] - best_fixed["expectancy"]
        if delta > 0:
            print(f"\n  >>> ATR WINS by {delta:+.4f}R per trade")
        elif delta < 0:
            print(f"\n  >>> FIXED % WINS by {abs(delta):.4f}R per trade")
        else:
            print(f"\n  >>> TIE -- both approaches equal")

        print(f"  >>> OVERALL BEST: {overall_best['stop_method']} "
              f"(Expectancy: {overall_best['expectancy']:+.4f}R)")

    return results


def regime_comparison(signals_df: pd.DataFrame, scanner_name: str, horizon: str = "5d"):
    """Compare within each market regime."""
    if "market_verdict" not in signals_df.columns:
        return

    for verdict in ["OFFENSIVE", "DEFENSIVE"]:
        regime_df = signals_df[signals_df["market_verdict"] == verdict].copy()
        if len(regime_df) < 50:
            continue
        print(f"\n  --- {verdict} regime only ({len(regime_df)} signals) ---")

        best_fixed_exp = -999
        best_fixed_name = ""
        best_atr_exp = -999
        best_atr_name = ""

        for pct in [2.0, 2.5, 3.0, 3.5, 4.0, 5.0]:
            regime_df[f"fixed_{pct}"] = pct
            r = simulate_stop(regime_df, f"fixed_{pct}", horizon)
            if r["n"] > 0 and r["expectancy"] > best_fixed_exp:
                best_fixed_exp = r["expectancy"]
                best_fixed_name = f"Fixed {pct}%"

        for mult in [1.0, 1.5, 2.0, 2.5, 3.0]:
            regime_df[f"atr_{mult}x"] = regime_df["atr_pct"] * mult
            r = simulate_stop(regime_df, f"atr_{mult}x", horizon)
            if r["n"] > 0 and r["expectancy"] > best_atr_exp:
                best_atr_exp = r["expectancy"]
                best_atr_name = f"ATR x{mult}"

        delta = best_atr_exp - best_fixed_exp
        winner = "ATR" if delta > 0 else "FIXED"
        print(f"    Best Fixed: {best_fixed_name} ({best_fixed_exp:+.4f}R) | "
              f"Best ATR: {best_atr_name} ({best_atr_exp:+.4f}R) | "
              f"Winner: {winner} (delta: {delta:+.4f}R)")


def main():
    """Run the ATR vs Fixed % stop comparison."""
    calibration_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "data", "calibration")

    print("=" * 75)
    print("  ATR-BASED vs FIXED % STOP-LOSS -- HEAD-TO-HEAD COMPARISON")
    print("  Using MAE data + live ATR(14) from OHLCV database")
    print("=" * 75)

    # --- EPISODIC PIVOT (primary alpha scanner) ---
    ep_files = sorted([f for f in os.listdir(calibration_dir)
                       if "episodic_pivot" in f and "signals" in f])
    if ep_files:
        latest = ep_files[-1]
        filepath = os.path.join(calibration_dir, latest)
        print(f"\n  Loading {latest}...")
        ep_df = pd.read_csv(filepath)
        print(f"  Loaded {len(ep_df)} EP signals")

        # Compute ATR for all EP signals
        ep_df = compute_atr_for_signals(ep_df)

        for horizon in ["3d", "5d", "10d"]:
            run_comparison(ep_df, "Episodic Pivot", horizon)
            regime_comparison(ep_df, "Episodic Pivot", horizon)

    # --- MOMENTUM BURST (high volume of signals) ---
    mb_files = sorted([f for f in os.listdir(calibration_dir)
                       if "momentum_burst" in f and "signals" in f])
    if mb_files:
        latest = mb_files[-1]
        filepath = os.path.join(calibration_dir, latest)
        filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"\n  Loading {latest} ({filesize_mb:.0f} MB)...")

        # Sample for MB (too large for full analysis)
        chunks = []
        for chunk in pd.read_csv(filepath, chunksize=20000):
            chunks.append(chunk)
            if len(chunks) >= 3:  # ~60k rows
                break
        mb_df = pd.concat(chunks, ignore_index=True)
        print(f"  Sampled {len(mb_df)} MB signals")

        mb_df = compute_atr_for_signals(mb_df)

        for horizon in ["3d", "5d"]:
            run_comparison(mb_df, "Momentum Burst", horizon)
            regime_comparison(mb_df, "Momentum Burst", horizon)

    print("\n" + "=" * 75)
    print("  CONCLUSION")
    print("=" * 75)
    print("""
  Compare the BEST FIXED row vs BEST ATR row for each scanner/horizon.
  If ATR consistently wins, it means adapting stops to each stock's
  volatility profile produces better results than a one-size-fits-all %.

  If FIXED wins or ties, the simpler approach is validated --
  use fixed % stops and save the complexity.
    """)


if __name__ == "__main__":
    main()
