"""Target and Exit optimization analysis using MFE (Maximum Favorable Excursion) data.

Analyzes historical signal data to find the optimal exit strategy:
1. Time-based exits (e.g., exit after 3, 5, 10 days)
2. Fixed % targets (e.g., sell at 5%, 10%, 15% gain)
3. Trailing stops (implied through MFE/MAE paths)

We want to maximize Expectancy (R-multiple) while reducing "giveback" 
(where a winner gives back its gains and hits the stop loss).
"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import config

# Recommended stops applied from our prior stop loss analysis
RECOMMENDED_STOPS = {
    "Episodic Pivot": config.TRADE_EP_STOP_PCT, # 4.0%
    "Momentum Burst": config.TRADE_MB_STOP_PCT, # 2.5%
    "Trend Intensity": config.TRADE_TI_STOP_PCT # 1.5%
}


def test_time_based_exits(df: pd.DataFrame, scanner_name: str, max_horizon: str = "20d"):
    """Evaluate pure time-based exits (holding for exactly K days)."""
    print(f"\n{'='*75}")
    print(f"  {scanner_name} -- Pure Time-Based Exits (No Stop Loss)")
    print(f"{'='*75}")
    
    horizons = ["1d", "3d", "5d", "10d", "20d"]
    results = {}
    
    # We must restrict to trades that have data for the maximum horizon to ensure apples-to-apples
    valid = df.dropna(subset=[f"return_{h}" for h in horizons]).copy()
    if valid.empty:
        print(f"  No valid data across all horizons.")
        return
        
    print(f"  Sample size: {len(valid)} trades\n")
    print(f"  {'Horizon':<8s} | {'Win Rate':>8s} | {'Avg Return':>10s} | {'Med Return':>10s} | {'Best P90':>9s}")
    print(f"  {'-'*8} | {'-'*8} | {'-'*10} | {'-'*10} | {'-'*9}")
    
    for h in horizons:
        ret_col = f"return_{h}"
        returns = valid[ret_col]
        win_rate = (returns > 0).mean() * 100
        avg_ret = returns.mean()
        med_ret = returns.median()
        p90_ret = np.percentile(returns, 90)
        
        print(f"  {h:<8s} | {win_rate:7.1f}% | {avg_ret:+9.2f}% | {med_ret:+9.2f}% | {p90_ret:+8.2f}%")
        results[h] = {"win_rate": win_rate, "avg_ret": avg_ret, "med_ret": med_ret}

    best_horizon = max(results.keys(), key=lambda k: results[k]["avg_ret"])
    print(f"\n  >>> BEST TIME EXIT: {best_horizon} holds (Highest Average Return)")


def test_fixed_targets_with_stops(df: pd.DataFrame, scanner_name: str, horizon: str = "10d"):
    """Evaluate fixed % targets combined with our optimized stop loss."""
    stop_pct = RECOMMENDED_STOPS.get(scanner_name, 2.5)
    
    print(f"\n{'='*75}")
    print(f"  {scanner_name} -- Fixed % Targets (Horizon: {horizon}, Stop: {stop_pct}%)")
    print(f"{'='*75}")
    
    mae_col = f"mae_{horizon}"
    mfe_col = f"mfe_{horizon}"
    return_col = f"return_{horizon}"
    
    valid = df.dropna(subset=[mae_col, mfe_col, return_col]).copy()
    if valid.empty:
        return
        
    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["peak_gain_pct"] = valid[mfe_col]
    
    # At this coarse level, we assume if MFE reached Target BEFORE MAE hit Stop, it's a win.
    # Since we only have max values over the period, we use a conservative heuristic:
    # If the peak gain > target AND drawdown < stop, it hit target.
    # If drawdown > stop, we assume it was stopped out before hitting the target (conservative).
    
    print(f"  {'Target%':>8s} | {'Hit Rate':>8s} | {'Stopped':>8s} | {'Expired':>8s} | {'Avg R':>7s} | {'Expectancy':>10s}")
    print(f"  {'-'*8} | {'-'*8} | {'-'*8} | {'-'*8} | {'-'*7} | {'-'*10}")
    
    targets = [3.0, 4.0, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0]
    best_expectancy = -999
    best_target = None
    
    for tgt in targets:
        # Simulate:
        # Condition 1: Hit stop -> -1R
        # Condition 2: Hit target (and didn't hit stop first) -> + (tgt / stop_pct) R
        # Condition 3: Expired (neither target nor stop hit) -> + (actual return / stop_pct) R
        
        stopped = valid["drawdown_pct"] > stop_pct
        hit_target = (~stopped) & (valid["peak_gain_pct"] >= tgt)
        expired = (~stopped) & (~hit_target)
        
        r_stopped = np.full(stopped.sum(), -1.0)
        r_target = np.full(hit_target.sum(), tgt / stop_pct)
        r_expired = valid.loc[expired, return_col] / stop_pct
        
        all_r = np.concatenate([r_stopped, r_target, r_expired])
        if len(all_r) == 0:
            continue
            
        win_count = np.sum(all_r > 0)
        total = len(all_r)
        win_rate = (win_count / total) * 100
        
        avg_win = float(np.mean(all_r[all_r > 0])) if win_count > 0 else 0
        avg_loss = float(np.mean(np.abs(all_r[all_r <= 0]))) if (total - win_count) > 0 else 0
        expectancy = ((win_rate / 100) * avg_win) - (((100 - win_rate) / 100) * avg_loss)
        avg_r = float(np.mean(all_r))
        
        print(f"  {tgt:7.1f}% | {hit_target.sum():8d} | {stopped.sum():8d} | {expired.sum():8d} | "
              f"{avg_r:+6.3f}R | {expectancy:+9.3f}R")
              
        if expectancy > best_expectancy:
            best_expectancy = expectancy
            best_target = tgt
            
    print(f"\n  >>> BEST FIXED TARGET: {best_target}% (Expectancy: {best_expectancy:+.3f}R)")


def test_trailing_stops(df: pd.DataFrame, scanner_name: str, horizon: str = "10d"):
    """Evaluate a simple moving profit target / trailing stop."""
    stop_pct = RECOMMENDED_STOPS.get(scanner_name, 2.5)
    
    print(f"\n{'='*75}")
    print(f"  {scanner_name} -- Trailing Stop Analysis (Horizon: {horizon})")
    print(f"{'='*75}")
    print(f"  Initial stop is {stop_pct}%. What if we move stop to breakeven after X% gain?")
    
    mae_col = f"mae_{horizon}"
    mfe_col = f"mfe_{horizon}"
    return_col = f"return_{horizon}"
    
    valid = df.dropna(subset=[mae_col, mfe_col, return_col]).copy()
    if valid.empty:
        return
        
    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["peak_gain_pct"] = valid[mfe_col]
    
    print(f"\n  *Note: Since we only have summary MFE/MAE and not daily paths,")
    print(f"   these are aggressive heuristics. We see how many trades hit X% then")
    print(f"   fell back to a negative return (giveback).")
    
    print(f"\n  {'Peak Gain Reached':>18s} | {'Total Trades':>13s} | {'Given Back to Loss':>20s}")
    print(f"  {'-'*18} | {'-'*13} | {'-'*20}")
    
    for peak in [2.0, 3.0, 4.0, 5.0, 7.5, 10.0]:
        reached_peak = valid["peak_gain_pct"] >= peak
        ended_negative = valid[return_col] < 0
        
        given_back = valid[reached_peak & ended_negative]
        total_reached = reached_peak.sum()
        
        if total_reached > 0:
            giveback_pct = len(given_back) / total_reached * 100
            print(f"  {peak:>17.1f}% | {total_reached:13d} | {len(given_back):11d} ({giveback_pct:4.1f}%)")


def analyze_mfe_distribution(df: pd.DataFrame, scanner_name: str):
    """Analyze the overall MFE distribution to understand typical run length."""
    print(f"\n{'='*75}")
    print(f"  {scanner_name} -- Maximum Favorable Excursion (MFE) Distribution")
    print(f"{'='*75}")
    
    horizons = ["3d", "5d", "10d", "20d"]
    
    print(f"  How high do candidates typically reach before the period ends?")
    print(f"\n  {'Horizon':<8s} | {'P25 (Weak)':>10s} | {'P50 (Median)':>12s} | {'P75 (Strong)':>12s} | {'P90 (Runners)':>13s}")
    print(f"  {'-'*8} | {'-'*10} | {'-'*12} | {'-'*12} | {'-'*13}")
    
    for h in horizons:
        mfe_col = f"mfe_{h}"
        if mfe_col not in df.columns:
            continue
            
        mfe = df[mfe_col].dropna()
        if mfe.empty:
            continue
            
        p25 = np.percentile(mfe, 25)
        p50 = np.percentile(mfe, 50)
        p75 = np.percentile(mfe, 75)
        p90 = np.percentile(mfe, 90)
        
        print(f"  {h:<8s} | {p25:>9.1f}% | {p50:>11.1f}% | {p75:>11.1f}% | {p90:>12.1f}%")


def main():
    calibration_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calibration")
    
    print("\n" + "=" * 75)
    print("  DHANUSTAMBHA TARGET & EXIT OPTIMIZATION ANALYSIS")
    print("=" * 75)
    
    scanners = {
        "Episodic Pivot": "episodic_pivot",
        "Momentum Burst": "momentum_burst",
        "Trend Intensity": "trend_intensity"
    }
    
    for name, file_pattern in scanners.items():
        files = sorted([f for f in os.listdir(calibration_dir) if file_pattern in f and "signals" in f])
        if not files:
            continue
            
        latest_file = files[-1]
        filepath = os.path.join(calibration_dir, latest_file)
        filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"\n\n===========================================================================")
        print(f"  ANALYZING {name.upper()}")
        print(f"===========================================================================")
        
        if filesize_mb > 50:
            chunks = []
            for chunk in pd.read_csv(filepath, chunksize=50000):
                chunks.append(chunk)
                if len(chunks) >= 4:  # ~200k rows
                    break
            df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.read_csv(filepath)
            
        analyze_mfe_distribution(df, name)
        test_time_based_exits(df, name)
        
        # Test targets assuming a 10-day hold (typical swing trading timeframe)
        for h in ["3d", "5d", "10d"]:
            test_fixed_targets_with_stops(df, name, h)
            
        test_trailing_stops(df, name, "10d")

if __name__ == "__main__":
    main()
