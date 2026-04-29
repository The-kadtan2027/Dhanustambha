"""MB feature analysis using return_5d (alpha not available in this signals file)."""
import pandas as pd
import numpy as np
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)

# Load all MB signals for the current live param set
print("Loading MB signals (this may take a moment for 236MB)...")
df = pd.read_csv(
    'data/calibration/2026-04-23-momentum_burst-NIFTY500-signals.csv',
    low_memory=False
)
print(f"Total MB signals: {len(df)}")

# Use live param set
pid = 'detect_momentum_burst:{"max_prior_run":15.0,"min_pct":5.0,"min_vol_ratio":1.5}'
mb = df[df['param_set_id'] == pid].drop_duplicates(subset=['date','symbol']).copy()
mb = mb.dropna(subset=['return_5d'])
print(f"Live param signals with valid 5d returns: {len(mb)}")

features = ['close_location_pct','range_expansion_ratio','nr_count_10d',
            'consolidation_days','prior_10d_run_pct','prior_20d_run_pct',
            'distance_from_20d_high_pct','trend_linearity_20d',
            'pct_change','volume_ratio']

# 1. Correlation with return_5d
print("\n=== FEATURE CORRELATION WITH return_5d ===")
for f in features:
    valid = mb[[f,'return_5d']].dropna()
    if len(valid) > 50:
        corr = valid[f].corr(valid['return_5d'])
        print(f"  {f:35s}  r = {corr:+.4f}  (n={len(valid)})")

# 2. Quintile analysis
print("\n=== QUINTILE ANALYSIS (by return_5d) ===")
for f in features:
    valid = mb[[f,'return_5d','return_10d']].dropna()
    if len(valid) < 100:
        continue
    try:
        valid['quintile'] = pd.qcut(valid[f], 5, labels=['Q1(low)','Q2','Q3','Q4','Q5(high)'], duplicates='drop')
    except ValueError:
        continue
    
    q = valid.groupby('quintile', observed=True).agg(
        count=('return_5d','count'),
        avg_return_5d=('return_5d','mean'),
        avg_return_10d=('return_10d','mean'),
        win_rate_5d=('return_5d', lambda x: (x>0).mean()*100),
    ).round(2)
    print(f"\n  --- {f} ---")
    print(f"  {q.to_string()}")

# 3. Composite filter tests
print("\n\n=== COMPOSITE FILTER TESTS ===")

baseline_return = mb['return_5d'].mean()
baseline_wr = (mb['return_5d'] > 0).mean() * 100
print(f"BASELINE (all MB signals): n={len(mb)}, avg_return_5d={baseline_return:.2f}%, win_rate={baseline_wr:.1f}%")

tests = {
    'A) Tight base (NR>=7, consol>=7)': 
        (mb['nr_count_10d'] >= 7) & (mb['consolidation_days'] >= 7),
    'B) Strong close (close_loc>=75%)': 
        mb['close_location_pct'] >= 75,
    'C) New 20d high (dist>=0)': 
        mb['distance_from_20d_high_pct'] >= 0,
    'D) Low prior run (prior_10d<=5%)': 
        mb['prior_10d_run_pct'] <= 5.0,
    'E) High vol (vol_ratio>=2.5x)':
        mb['volume_ratio'] >= 2.5,
    'F) Tight+Strong (NR>=6, close>=70)':
        (mb['nr_count_10d'] >= 6) & (mb['close_location_pct'] >= 70),
    'G) Tight+Strong+NewHigh':
        (mb['nr_count_10d'] >= 6) & (mb['close_location_pct'] >= 70) & (mb['distance_from_20d_high_pct'] >= 0),
    'H) Tight+Strong+NewHigh+HighVol':
        (mb['nr_count_10d'] >= 6) & (mb['close_location_pct'] >= 70) & (mb['distance_from_20d_high_pct'] >= 0) & (mb['volume_ratio'] >= 2.0),
    'I) Strong+HighVol+Fresh':
        (mb['close_location_pct'] >= 70) & (mb['volume_ratio'] >= 2.5) & (mb['prior_10d_run_pct'] <= 8.0),
    'J) Tight+Strong+Fresh+HighVol':
        (mb['nr_count_10d'] >= 5) & (mb['close_location_pct'] >= 65) & (mb['prior_10d_run_pct'] <= 5.0) & (mb['volume_ratio'] >= 2.0),
    'K) Linear trend + breakout':
        (mb['trend_linearity_20d'] >= 0.6) & (mb['distance_from_20d_high_pct'] >= 0) & (mb['volume_ratio'] >= 1.8),
}

print()
for name, mask in tests.items():
    subset = mb[mask]
    if len(subset) >= 10:
        r5 = subset['return_5d'].dropna()
        r10 = subset['return_10d'].dropna()
        h5 = subset['hit_5pct_by_5d'].dropna()
        h8 = subset['hit_8pct_by_10d'].dropna()
        f3 = subset['failed_to_gain_by_3d'].dropna()
        mfe5 = subset['mfe_5d'].dropna()
        mae5 = subset['mae_5d'].dropna()
        mfe_mae = abs(mfe5.mean()/mae5.mean()) if mae5.mean() != 0 else 0
        print(f"{name}")
        print(f"  n={len(subset):5d}  5d_avg={r5.mean():+.2f}%  10d_avg={r10.mean():+.2f}%  "
              f"wr5d={( r5>0).mean()*100:.1f}%  hit5%by5d={h5.mean()*100:.1f}%  "
              f"hit8%by10d={h8.mean()*100:.1f}%  fail3d={f3.mean()*100:.1f}%  "
              f"MFE/MAE={mfe_mae:.2f}")
    else:
        print(f"{name}: only {len(subset)} signals (too few)")
    print()

# 4. Best combo - show per-year consistency
print("\n=== BEST COMBO YEARLY CONSISTENCY ===")
best_mask = (mb['nr_count_10d'] >= 6) & (mb['close_location_pct'] >= 70) & (mb['distance_from_20d_high_pct'] >= 0)
best = mb[best_mask].copy()
best['year'] = pd.to_datetime(best['date']).dt.year
if len(best) > 20:
    yearly = best.groupby('year').agg(
        count=('return_5d', 'count'),
        avg_return_5d=('return_5d', 'mean'),
        avg_return_10d=('return_10d', 'mean'),
        win_rate_5d=('return_5d', lambda x: (x>0).mean()*100),
    ).round(2)
    print(yearly.to_string())
