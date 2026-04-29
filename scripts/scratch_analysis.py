"""Scratch analysis script — deep dive into where the edge actually is."""
import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)

df = pd.read_csv('data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv')

LIVE_PARAM = 'detect_episodic_pivot:{"max_days_since_gap":2,"min_gap_pct":5.0,"min_gap_vol_ratio":3.0}'
TIGHT_PARAM = 'detect_episodic_pivot:{"max_days_since_gap":1,"min_gap_pct":8.0,"min_gap_vol_ratio":4.0}'

for label, pid in [("LIVE (5.0/3.0/2)", LIVE_PARAM), ("TIGHT (8.0/4.0/1)", TIGHT_PARAM)]:
    subset = df[df['param_set_id'] == pid].drop_duplicates(subset=['date','symbol'])
    print(f"\n{'='*60}")
    print(f"  {label}: {len(subset)} unique signals")
    print(f"{'='*60}")
    
    # Regime distribution
    if 'market_verdict' in subset.columns:
        print("\n--- Regime Distribution ---")
        regime = subset.groupby('market_verdict').agg(
            count=('symbol','count'),
            avg_return_5d=('return_5d','mean'),
            median_return_5d=('return_5d','median'),
            avg_alpha_5d=('alpha_5d','mean'),
            avg_return_10d=('return_10d','mean'),
            avg_alpha_10d=('alpha_10d','mean'),
            avg_return_20d=('return_20d','mean'),
            hit_5pct_by_5d=('hit_5pct_by_5d', lambda x: x.mean()*100),
            hit_8pct_by_10d=('hit_8pct_by_10d', lambda x: x.mean()*100),
            failed_by_3d=('failed_to_gain_by_3d', lambda x: x.mean()*100),
        ).round(2)
        print(regime.to_string())

    # Overall stats
    print("\n--- Overall Forward Returns ---")
    for h in [5, 10, 20]:
        col = f'return_{h}d'
        acol = f'alpha_{h}d'
        valid = subset[col].dropna()
        avalid = subset[acol].dropna()
        wr = (valid>0).mean()*100
        print(f"  {h}d: avg={valid.mean():.2f}%, median={valid.median():.2f}%, "
              f"win_rate={wr:.1f}%, avg_alpha={avalid.mean():.2f}%")

    print("\n--- Profit Target Hit Rates ---")
    for col in ['hit_2pct_by_3d','hit_5pct_by_5d','hit_8pct_by_10d']:
        valid = subset[col].dropna()
        print(f"  {col}: {valid.mean()*100:.1f}%")

    print("\n--- Failure Speed ---")
    for col in ['failed_to_gain_by_3d','failed_to_gain_by_5d']:
        valid = subset[col].dropna()
        print(f"  {col}: {valid.mean()*100:.1f}%")

    print("\n--- MFE/MAE ---")
    for h in [3, 5, 10]:
        mfe = subset[f'mfe_{h}d'].dropna()
        mae = subset[f'mae_{h}d'].dropna()
        ratio = abs(mfe.mean()/mae.mean()) if mae.mean() != 0 else 0
        print(f"  {h}d: avg_MFE={mfe.mean():.2f}%, avg_MAE={mae.mean():.2f}%, MFE/MAE={ratio:.2f}")

    # OFFENSIVE only
    off = subset[subset['market_verdict']=='OFFENSIVE']
    if len(off) > 0:
        print(f"\n--- OFFENSIVE Regime Only ({len(off)} signals) ---")
        for h in [5, 10, 20]:
            col = f'return_{h}d'
            valid = off[col].dropna()
            avalid = off[f'alpha_{h}d'].dropna()
            wr = (valid>0).mean()*100
            print(f"  {h}d: avg={valid.mean():.2f}%, median={valid.median():.2f}%, "
                  f"win_rate={wr:.1f}%, avg_alpha={avalid.mean():.2f}%")
        for col in ['hit_5pct_by_5d','hit_8pct_by_10d']:
            valid = off[col].dropna()
            print(f"  {col}: {valid.mean()*100:.1f}%")

    # Day-0 entries only
    if 'days_since_gap' in subset.columns:
        day0 = subset[subset['days_since_gap']==0]
        print(f"\n--- Day-0 (Gap Day) Entries Only ({len(day0)} signals) ---")
        for h in [5, 10, 20]:
            col = f'return_{h}d'
            valid = day0[col].dropna()
            avalid = day0[f'alpha_{h}d'].dropna()
            wr = (valid>0).mean()*100
            print(f"  {h}d: avg={valid.mean():.2f}%, median={valid.median():.2f}%, "
                  f"win_rate={wr:.1f}%, avg_alpha={avalid.mean():.2f}%")

# Day-0 OFFENSIVE only for live params
print(f"\n{'='*60}")
print(f"  SWEET SPOT: Day-0 + OFFENSIVE (Live params)")
print(f"{'='*60}")
live = df[df['param_set_id'] == LIVE_PARAM].drop_duplicates(subset=['date','symbol'])
sweet = live[(live['days_since_gap']==0) & (live['market_verdict']=='OFFENSIVE')]
print(f"Signals: {len(sweet)}")
if len(sweet) > 0:
    for h in [5, 10, 20]:
        col = f'return_{h}d'
        valid = sweet[col].dropna()
        avalid = sweet[f'alpha_{h}d'].dropna()
        wr = (valid>0).mean()*100
        print(f"  {h}d: avg={valid.mean():.2f}%, median={valid.median():.2f}%, "
              f"win_rate={wr:.1f}%, avg_alpha={avalid.mean():.2f}%")
    for col in ['hit_5pct_by_5d','hit_8pct_by_10d']:
        valid = sweet[col].dropna()
        print(f"  {col}: {valid.mean()*100:.1f}%")
    for col in ['failed_to_gain_by_3d']:
        valid = sweet[col].dropna()
        print(f"  {col}: {valid.mean()*100:.1f}%")

# MB comparison — best params
print(f"\n{'='*60}")
print(f"  MOMENTUM BURST — Best Regime Split")
print(f"{'='*60}")
try:
    mb = pd.read_csv('data/calibration/2026-04-25-momentum_burst-NIFTY500-summary.csv')
    # Top 3 by offensive alpha
    mb_sorted = mb.sort_values('offensive_avg_alpha_5d', ascending=False)
    cols = ['param_set_id','n_signals','avg_alpha_5d','median_alpha_5d',
            'offensive_n','offensive_avg_alpha_5d','offensive_win_rate_5d',
            'defensive_n','defensive_avg_alpha_5d',
            'avoid_n','avoid_avg_alpha_5d']
    available = [c for c in cols if c in mb_sorted.columns]
    print("Top 5 MB params by OFFENSIVE alpha:")
    print(mb_sorted[available].head(5).to_string())
except Exception as e:
    print(f"Error: {e}")

# TI comparison  
print(f"\n{'='*60}")
print(f"  TREND INTENSITY — Best Regime Split")
print(f"{'='*60}")
try:
    ti = pd.read_csv('data/calibration/2026-04-25-trend_intensity-NIFTY500-summary.csv')
    ti_sorted = ti.sort_values('offensive_avg_alpha_5d', ascending=False)
    cols = ['param_set_id','n_signals','avg_alpha_5d','median_alpha_5d',
            'offensive_n','offensive_avg_alpha_5d','offensive_win_rate_5d',
            'defensive_n','defensive_avg_alpha_5d',
            'avoid_n','avoid_avg_alpha_5d']
    available = [c for c in cols if c in ti_sorted.columns]
    print("Top 5 TI params by OFFENSIVE alpha:")
    print(ti_sorted[available].head(5).to_string())
except Exception as e:
    print(f"Error: {e}")
