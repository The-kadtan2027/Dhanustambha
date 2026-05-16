"""Stop-loss optimization analysis using MAE (Maximum Adverse Excursion) data.

# Force UTF-8 output on Windows

Analyzes historical signal data to find the optimal stop-loss percentage that:
1. Lets winners breathe (doesn't prematurely exit profitable trades)
2. Cuts losers fast (stops out of failing trades quickly)
3. Maximizes risk-adjusted returns (best R-multiple distribution)

Uses the 80th-percentile MAE rule: set stop just beyond the level that
80% of your winners survived through.
"""

import sys
import os
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np


def analyze_mae_distribution(df: pd.DataFrame, scanner_name: str, horizon: str = "5d") -> dict:
    """Analyze MAE distribution for winners vs losers at a given horizon."""
    mae_col = f"mae_{horizon}"
    mfe_col = f"mfe_{horizon}"
    return_col = f"return_{horizon}"
    
    valid = df.dropna(subset=[mae_col, mfe_col, return_col]).copy()
    if valid.empty:
        print(f"  No valid data for {scanner_name} @ {horizon}")
        return {}
    
    # MAE is already negative (it's the min low vs entry), make it a positive drawdown
    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["is_winner"] = valid[return_col] > 0
    
    winners = valid[valid["is_winner"]]
    losers = valid[~valid["is_winner"]]
    
    print(f"\n{'='*70}")
    print(f"  {scanner_name} — {horizon} horizon")
    print(f"{'='*70}")
    print(f"  Total signals: {len(valid)}")
    print(f"  Winners: {len(winners)} ({len(winners)/len(valid)*100:.1f}%)")
    print(f"  Losers:  {len(losers)} ({len(losers)/len(valid)*100:.1f}%)")
    
    # --- WINNERS: How much drawdown did they endure? ---
    if not winners.empty:
        print(f"\n  WINNERS — Max drawdown they survived:")
        for pct in [25, 50, 75, 80, 90, 95]:
            val = np.percentile(winners["drawdown_pct"], pct)
            print(f"    P{pct:2d}: {val:.2f}%")
        print(f"    Mean: {winners['drawdown_pct'].mean():.2f}%")
        print(f"    Max:  {winners['drawdown_pct'].max():.2f}%")
    
    # --- LOSERS: How quickly did they show they were failing? ---
    if not losers.empty:
        print(f"\n  LOSERS — How deep they went:")
        for pct in [25, 50, 75, 80, 90, 95]:
            val = np.percentile(losers["drawdown_pct"], pct)
            print(f"    P{pct:2d}: {val:.2f}%")
        print(f"    Mean: {losers['drawdown_pct'].mean():.2f}%")
    
    # --- STOP-LOSS SIMULATION ---
    print(f"\n  STOP-LOSS SIMULATION (what if we'd used X% stop?):")
    print(f"  {'SL%':>6s} | {'Saved':>6s} | {'Stopped':>7s} | {'Winners':>7s} | {'Losers':>6s} | {'Net':>8s} | {'Avg R':>6s} | {'Expectancy':>10s}")
    print(f"  {'-'*6} | {'-'*6} | {'-'*7} | {'-'*7} | {'-'*6} | {'-'*8} | {'-'*6} | {'-'*10}")
    
    best_expectancy = -999
    best_sl = None
    results = {}
    
    for sl_pct in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]:
        # Winners that would have been stopped out (false stops)
        winners_stopped = winners[winners["drawdown_pct"] > sl_pct]
        winners_kept = winners[winners["drawdown_pct"] <= sl_pct]
        
        # Losers that would have been stopped out (true stops — saved money)
        losers_stopped = losers[losers["drawdown_pct"] > sl_pct]
        losers_survived = losers[losers["drawdown_pct"] <= sl_pct]
        
        # P&L simulation
        # Winners kept: they earn their actual return
        # Winners stopped out: they lose sl_pct (false exit)
        # Losers stopped: they lose sl_pct (capped loss)
        # Losers survived: this shouldn't happen often with tight stops but...
        #   they lose their actual return (which is negative but < sl_pct)
        
        total_trades = len(valid)
        
        # R-multiple calculation: R = sl_pct (our risk unit)
        # Winner kept: gain = return / sl_pct (in R)
        # Winner stopped: loss = -1R
        # Loser stopped: loss = -1R
        # Loser survived (drawdown < SL but still a loser at horizon end): actual loss / sl_pct
        
        r_values = []
        if not winners_kept.empty:
            r_values.extend((winners_kept[return_col] / sl_pct).tolist())
        if not winners_stopped.empty:
            r_values.extend([-1.0] * len(winners_stopped))
        if not losers_stopped.empty:
            r_values.extend([-1.0] * len(losers_stopped))
        if not losers_survived.empty:
            r_values.extend((losers_survived[return_col] / sl_pct).tolist())
        
        if r_values:
            r_arr = np.array(r_values)
            avg_r = np.mean(r_arr)
            win_count = np.sum(r_arr > 0)
            loss_count = np.sum(r_arr <= 0)
            win_rate = win_count / len(r_arr) * 100
            
            avg_win = np.mean(r_arr[r_arr > 0]) if win_count > 0 else 0
            avg_loss = np.mean(np.abs(r_arr[r_arr <= 0])) if loss_count > 0 else 0
            expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
        else:
            avg_r = 0
            expectancy = 0
        
        saved_from_losers = len(losers_stopped)
        false_stops = len(winners_stopped)
        net_benefit = saved_from_losers - false_stops
        
        print(f"  {sl_pct:5.1f}% | {saved_from_losers:5d}L | {false_stops:6d}W | "
              f"{len(winners_kept):6d}W | {len(losers_stopped):5d}L | "
              f"{net_benefit:+7d}  | {avg_r:+5.2f}R | {expectancy:+9.3f}R")
        
        results[sl_pct] = {
            "sl_pct": sl_pct,
            "winners_kept": len(winners_kept),
            "winners_stopped": len(winners_stopped),
            "losers_stopped": len(losers_stopped),
            "losers_survived": len(losers_survived),
            "avg_r": avg_r,
            "expectancy": expectancy,
            "net_benefit": net_benefit,
        }
        
        if expectancy > best_expectancy:
            best_expectancy = expectancy
            best_sl = sl_pct
    
    print(f"\n  >>> OPTIMAL STOP-LOSS: {best_sl}% (Expectancy: {best_expectancy:+.3f}R)")
    
    # --- MFE/MAE Ratio Analysis ---
    print(f"\n  MFE/MAE RATIO (reward-to-pain — higher is better):")
    valid["mfe_mae_ratio"] = valid[mfe_col] / valid["drawdown_pct"].replace(0, np.nan)
    for tier_name, tier_mask in [("All", pd.Series(True, index=valid.index)),
                                  ("Winners", valid["is_winner"]),
                                  ("Losers", ~valid["is_winner"])]:
        subset = valid[tier_mask]
        ratio = subset["mfe_mae_ratio"].dropna()
        if not ratio.empty:
            print(f"    {tier_name:8s}: median={ratio.median():.2f}, mean={ratio.mean():.2f}")
    
    return results


def analyze_by_regime(df: pd.DataFrame, scanner_name: str, horizon: str = "5d"):
    """Break down optimal SL by market regime."""
    mae_col = f"mae_{horizon}"
    return_col = f"return_{horizon}"
    
    valid = df.dropna(subset=[mae_col, return_col, "market_verdict"]).copy()
    if valid.empty:
        return
    
    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["is_winner"] = valid[return_col] > 0
    
    print(f"\n  REGIME BREAKDOWN — {scanner_name} @ {horizon}:")
    for verdict in ["OFFENSIVE", "DEFENSIVE", "AVOID"]:
        regime = valid[valid["market_verdict"] == verdict]
        if regime.empty:
            continue
        winners = regime[regime["is_winner"]]
        
        if not winners.empty:
            p80 = np.percentile(winners["drawdown_pct"], 80)
            median_mae = winners["drawdown_pct"].median()
            print(f"    {verdict:11s}: {len(regime):4d} signals, "
                  f"{len(winners)/len(regime)*100:.0f}% win rate, "
                  f"Winner P80 MAE: {p80:.2f}%, "
                  f"Median MAE: {median_mae:.2f}%")


def analyze_by_tier(df: pd.DataFrame, scanner_name: str, horizon: str = "5d"):
    """Break down optimal SL by quality tier (A+ vs B, HIGH vs standard)."""
    mae_col = f"mae_{horizon}"
    return_col = f"return_{horizon}"
    
    valid = df.dropna(subset=[mae_col, return_col]).copy()
    if valid.empty:
        return
    
    valid["drawdown_pct"] = valid[mae_col].abs()
    valid["is_winner"] = valid[return_col] > 0
    
    # Check for tier/quality columns
    tier_col = None
    if "tier" in valid.columns:
        tier_col = "tier"
    elif "quality" in valid.columns:
        tier_col = "quality"
    
    if tier_col and valid[tier_col].notna().any():
        print(f"\n  QUALITY TIER BREAKDOWN — {scanner_name} @ {horizon}:")
        for tier_val in valid[tier_col].dropna().unique():
            tier = valid[valid[tier_col] == tier_val]
            winners = tier[tier["is_winner"]]
            if not winners.empty:
                p80 = np.percentile(winners["drawdown_pct"], 80)
                print(f"    {str(tier_val):6s}: {len(tier):4d} signals, "
                      f"{len(winners)/len(tier)*100:.0f}% wr, "
                      f"Winner P80 MAE: {p80:.2f}%")


def main():
    """Run stop-loss analysis on all available signal data."""
    calibration_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "data", "calibration")
    
    # Use the latest signal files for each scanner
    # EP signals — where our proven alpha lives
    ep_files = sorted([f for f in os.listdir(calibration_dir) 
                       if "episodic_pivot" in f and "signals" in f])
    mb_files = sorted([f for f in os.listdir(calibration_dir)
                       if "momentum_burst" in f and "signals" in f])
    ti_files = sorted([f for f in os.listdir(calibration_dir)
                       if "trend_intensity" in f and "signals" in f])
    
    print("=" * 70)
    print("  DHANUSTAMBHA STOP-LOSS OPTIMIZATION ANALYSIS")
    print("  Using MAE (Maximum Adverse Excursion) from historical signals")
    print("=" * 70)
    
    for scanner_name, files in [("Episodic Pivot", ep_files),
                                 ("Momentum Burst", mb_files),
                                 ("Trend Intensity", ti_files)]:
        if not files:
            print(f"\n  No signal files found for {scanner_name}")
            continue
        
        latest_file = files[-1]
        filepath = os.path.join(calibration_dir, latest_file)
        filesize_mb = os.path.getsize(filepath) / (1024 * 1024)
        print(f"\n  Loading {latest_file} ({filesize_mb:.1f} MB)...")
        
        # For very large files (MB signals ~247MB), sample
        if filesize_mb > 50:
            # Read with chunking — take a representative sample
            chunks = []
            for chunk in pd.read_csv(filepath, chunksize=50000):
                chunks.append(chunk)
                if len(chunks) >= 10:  # ~500k rows max
                    break
            df = pd.concat(chunks, ignore_index=True)
            print(f"  Sampled {len(df)} rows (file too large for full read)")
        else:
            df = pd.read_csv(filepath)
            print(f"  Loaded {len(df)} rows")
        
        # Filter to the best parameter set (the one we actually use in live)
        # For EP: our live params are min_gap_pct=5.0, min_gap_vol_ratio=3.0, max_days_since_gap=2
        # For now, analyze ALL parameter sets combined for the MAE distribution,
        # then also break down by the live param set
        
        for horizon in ["3d", "5d", "10d"]:
            results = analyze_mae_distribution(df, scanner_name, horizon)
            analyze_by_regime(df, scanner_name, horizon)
            analyze_by_tier(df, scanner_name, horizon)
    
    # Final recommendation
    print("\n" + "=" * 70)
    print("  SUMMARY & RECOMMENDATIONS")
    print("=" * 70)
    print("""
  The optimal stop-loss should be based on the P80 MAE of WINNERS:
  - Set your stop just beyond the drawdown that 80% of winners survived
  - This lets most winners breathe while cutting losers at their typical 
    failure point
  
  KEY PRINCIPLE (from MAE research):
  - If 80% of your winners never dip more than X%, then a stop at X% 
    would only prematurely exit 20% of winners while catching most losers
  - The 'sweet spot' is where expectancy (win_rate * avg_win - loss_rate * avg_loss)
    is maximized
    
  COMPARE WITH YOUR CURRENT 2.5% STOP:
  - Check the 2.5% row in each scanner's simulation table above
  - If it has excessive 'Winners Stopped', your stop is too tight
  - If 'Losers Survived' is high, your stop is too loose
    """)


if __name__ == "__main__":
    main()
