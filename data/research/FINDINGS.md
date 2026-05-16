# Stream G Research Findings

## 2026-05-07 - EP G2 feature-filter validation

### Input

- Scanner: `episodic_pivot`
- Universe: `NIFTY500`
- Calibration window: `2025-01-01` to `2025-06-30`
- Baseline summary: `data/calibration/2026-04-25-episodic_pivot-NIFTY500-summary.csv`
- Feature report: `data/research/2026-05-07-episodic_pivot-feature-analysis.md`

### Compact G2 checks

Saved outputs:

- `data/research/g2/ep-g2-gap_pct-ge-9_1-summary.csv`
- `data/research/g2/ep-g2-gap_vol_ratio-le-4_9-summary.csv`
- `data/research/g2/ep-g2-prior_65d_weakness_pct-ge-37-summary-smoke10.csv`

Results:

| Filter | Best 10-set n | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | Read |
|---|---:|---:|---:|---:|---:|---|
| `gap_pct>=9.1` | 52 | -0.04 | 59.6 | 21 | 71.4 | Improves hit rate, but median alpha remains weak. |
| `gap_vol_ratio<=4.9` | 107 | 1.58 | 61.7 | 47 | 68.1 | Solid, broad improvement with healthy signal count. |
| `prior_65d_weakness_pct>=37` | 32 | 2.34 | 81.2 | 20 | 85.0 | Strongest compact result. |

### Full G2 validation: `prior_65d_weakness_pct>=37`

Saved outputs:

- `data/research/g2/ep-g2-prior_65d_weakness_pct-ge-37-summary-full64.csv`
- `data/research/g2/ep-g2-prior_65d_weakness_pct-ge-37-signals-full64.csv`

Top full-grid rows:

| min_gap_pct | min_gap_vol_ratio | max_days_since_gap | Filtered signals | Raw signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | OFFENSIVE avg alpha 5d |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 6.0 | 3.0 | 2 | 12 | 50 | 9.55 | 100.0 | 8 | 100.0 | 10.64 |
| 6.0 | 3.0 | 1 | 8 | 33 | 9.55 | 100.0 | 5 | 100.0 | 11.93 |
| 6.0 | 3.0 | 3 | 17 | 72 | 7.73 | 94.1 | 10 | 100.0 | 10.05 |
| 5.0 | 3.0 | 2 | 14 | 78 | 7.03 | 85.7 | 9 | 88.9 | 9.32 |
| 6.0 | 3.0 | 5 | 26 | 117 | 6.44 | 88.5 | 15 | 86.7 | 7.41 |

### Interpretation

`prior_65d_weakness_pct>=37` passes the G2 alpha-improvement gate decisively on the Jan-Jun 2025 window. The strongest practical candidate is:

- `min_gap_pct=6.0`
- `min_gap_vol_ratio=3.0`
- `max_days_since_gap=3`
- `prior_65d_weakness_pct>=37`

This candidate balances strength and count better than the top-ranked 12-signal row:

- `17` filtered signals from `72` raw signals
- `10` OFFENSIVE signals
- `median_alpha_5d = 7.73`
- `win_rate_5d = 94.1`
- `OFFENSIVE win_rate_5d = 100.0`
- `OFFENSIVE avg_alpha_5d = 10.05`

### Decision

Do not promote directly to live scanner defaults yet. The result is strong but based on a six-month window and small filtered counts. Next validation should check a longer or out-of-sample window before changing `config.py` or `detect_episodic_pivot()`.

## 2026-05-07 - EP out-of-sample validation on 2025-H2

### Setup

- OOS window: `2025-07-01` to `2025-12-31`
- Breadth context: backfilled `126` trading days for this window before validation
- Purpose: test whether Jan-Jun 2025 G2 feature filters generalize before live promotion

### Exact practical G2 winner: `prior_65d_weakness_pct>=37`

Saved outputs:

- `data/research/g2/ep-oos-2025h2-prior_65d_weakness-ge-37-summary.csv`
- `data/research/g2/ep-oos-2025h2-prior_65d_weakness-ge-37-filtered-signals.csv`

Parameters:

- `min_gap_pct=6.0`
- `min_gap_vol_ratio=3.0`
- `max_days_since_gap=3`

Result:

| Case | Signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | Read |
|---|---:|---:|---:|---:|---:|---|
| Unfiltered | 54 | 0.24 | 57.4 | 7 | 42.9 | Baseline was modest, and OFFENSIVE behavior was poor. |
| Filtered | 1 | -6.70 | 0.0 | 0 | 0.0 | Fails OOS due to no usable signal count and a losing lone signal. |

Decision: `prior_65d_weakness_pct>=37` is rejected for live promotion despite strong Jan-Jun 2025 fit.

### Runner-up checks

Saved outputs:

- `data/research/g2/ep-oos-2025h2-gap_vol_ratio-le-4_9-summary.csv`
- `data/research/g2/ep-oos-2025h2-gap_vol_ratio-le-4_9-filtered-signals.csv`
- `data/research/g2/ep-oos-2025h2-gap_pct-ge-9_1-summary.csv`
- `data/research/g2/ep-oos-2025h2-gap_pct-ge-9_1-filtered-signals.csv`

Results:

| Filter | Parameters | Filtered signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | Read |
|---|---|---:|---:|---:|---:|---:|---|
| `gap_vol_ratio<=4.9` | `4.0 / 3.0 / 2` | 10 | 2.12 | 70.0 | 2 | 100.0 | Best OOS behavior, but too few OFFENSIVE signals to promote. |
| `gap_pct>=9.1` | `4.0 / 3.0 / 5` | 26 | -0.15 | 53.8 | 4 | 50.0 | Improves hit rate slightly but not alpha; reject for now. |

### Recommendation

Do not change live EP defaults yet. The current evidence says:

1. The strongest Jan-Jun feature (`prior_65d_weakness_pct>=37`) was overfit.
2. `gap_vol_ratio<=4.9` deserves more validation because it preserved positive OOS median alpha, but the 2025-H2 OFFENSIVE sample is only `2` signals.
3. The next research step should validate `gap_vol_ratio<=4.9` across a longer combined window or a rolling split, and only consider live promotion if OFFENSIVE counts become large enough to trust.

## 2026-05-07 - Rolling validation for `gap_vol_ratio<=4.9`

### Setup

- Parameters: `min_gap_pct=4.0`, `min_gap_vol_ratio=3.0`, `max_days_since_gap=2`
- Filter: `gap_vol_ratio<=4.9`
- Windows: 2025-H1, 2025-H2, full 2025

Saved outputs:

- `data/research/g2/ep-rolling-gap_vol_ratio-le-4_9-summary.csv`
- `data/research/g2/ep-2025h1-gap_vol_ratio-le-4_9-filtered-signals.csv`
- `data/research/g2/ep-2025h2-gap_vol_ratio-le-4_9-filtered-signals.csv`
- `data/research/g2/ep-2025full-gap_vol_ratio-le-4_9-filtered-signals.csv`

### Results

| Window | Case | Signals | Raw signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | OFFENSIVE avg alpha 5d |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-H1 | Unfiltered | 132 | - | 0.32 | 59.1 | 59 | 71.2 | 1.49 |
| 2025-H1 | Filtered | 52 | 132 | 1.04 | 69.2 | 23 | 87.0 | 3.54 |
| 2025-H2 | Unfiltered | 109 | - | 0.27 | 49.5 | 24 | 45.8 | -2.99 |
| 2025-H2 | Filtered | 10 | 109 | 2.12 | 70.0 | 2 | 100.0 | 3.73 |
| Full 2025 | Unfiltered | 254 | - | 0.25 | 53.5 | 84 | 63.1 | 0.17 |
| Full 2025 | Filtered | 62 | 254 | 1.37 | 69.4 | 25 | 88.0 | 3.55 |

### Interpretation

`gap_vol_ratio<=4.9` is the first EP feature filter that survives a rolling sanity check:

- It improved full-2025 median alpha from `0.25` to `1.37`.
- It improved full-2025 win rate from `53.5` to `69.4`.
- It improved OFFENSIVE win rate from `63.1` to `88.0`.
- It retained `25` OFFENSIVE signals in full 2025, enough for a stronger signal than the earlier one-period checks.

The weak point is H2 OFFENSIVE count: only `2` filtered OFFENSIVE signals, so H2 alone cannot prove regime stability.

### Recommendation

Promote `gap_vol_ratio<=4.9` from "interesting" to "candidate live quality filter", but do not hard-code it directly into live EP detection yet.

Next implementation step should add a configurable, disabled-by-default EP quality filter:

- `EP_MAX_GAP_VOLUME_RATIO = 0.0`
- `0.0` means disabled and preserves current live behavior
- a research/paper-trading run can set it to `4.9` to observe candidate flow before making it a default

This gives us live observation without silently removing EP candidates from the normal daily briefing.

## 2026-05-07 - MB Task 7 HIGH-tier smoke validation

### Setup

- Scanner: `momentum_burst`
- Universe: `NIFTY500`
- Window: `2025-01-01` to `2025-06-30`
- Parameter sets: first `10` Stream D MB grid sets
- Baseline outputs:
  - `data/research/g2/mb-g2-unfiltered-summary-smoke10.csv`
  - `data/research/g2/mb-g2-unfiltered-signals-smoke10.csv`
- HIGH-filter outputs:
  - `data/research/g2/mb-g2-mb_quality-high-summary-smoke10.csv`
  - `data/research/g2/mb-g2-mb_quality-high-signals-smoke10.csv`
- Feature report:
  - `data/research/2026-05-07-momentum_burst-feature-analysis.md`

### Results

The unfiltered smoke baseline remained weak:

| Case | Signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | OFFENSIVE avg alpha 5d |
|---|---:|---:|---:|---:|---:|---:|
| Best unfiltered 10-set row | 2588 | -0.69 | 48.1 | 1163 | 52.9 | 0.12 |
| `mb_quality:HIGH` best 10-set row | 7 | -1.04 | 57.1 | 3 | 66.7 | 2.03 |

The fresh unfiltered feature-bucket report showed:

| Feature | Regime | Spread | Read |
|---|---|---:|---|
| `mb_quality` | all | 8.3pp | HIGH improved hit rate but had only `68` signals and worse average 5d alpha than STANDARD. |
| `mb_quality` | OFFENSIVE | 11.9pp | HIGH improved OFFENSIVE win rate and alpha, but only `28` signals and stayed below the `15pp` promotion gate. |
| `prior_10d_run_pct` | OFFENSIVE | 14.4pp | Interesting but still below the promotion gate. |
| `range_expansion_ratio` | OFFENSIVE | 13.6pp | Interesting but still below the promotion gate. |

### Decision

Do not harden MB HIGH quality into live detection from this evidence. It fails the Stream G Task 7 gate because `mb_quality` does not reach the `15pp` win-rate spread threshold and the HIGH sample is small.

Do not immediately demote Momentum Burst to reference-only from this smoke alone. The evidence supports "no hardening yet"; reference-only demotion should be decided after either a full-grid MB G2 run or an explicit product decision to remove low-alpha scanners from the main watchlist.

## 2026-05-07 - TI Task 10 relative-strength smoke validation

### Setup

- Scanner: `trend_intensity`
- Universe: `NIFTY500`
- Window: `2025-01-01` to `2025-06-30`
- Parameter sets: first `10` Stream D TI grid sets
- Code fix: TI prepared-history now receives benchmark history before feature preparation, so `relative_strength_vs_benchmark_3m` is populated instead of all-null.
- Baseline outputs:
  - `data/research/g2/ti-g2-unfiltered-summary-smoke10.csv`
  - `data/research/g2/ti-g2-unfiltered-signals-smoke10.csv`
- RS-band outputs:
  - `data/research/g2/ti-g2-rs-band-summary-smoke10.csv`
  - `data/research/g2/ti-g2-rs-band-signals-smoke10.csv`
- Feature reports:
  - `data/research/g2/ti-feature-analysis-all-smoke10.md`
  - `data/research/g2/ti-feature-analysis-offensive-smoke10.md`

### Results

The fresh baseline remained weak overall:

| Case | Signals | Median alpha 5d | Win rate 5d | OFFENSIVE signals | OFFENSIVE win rate 5d | OFFENSIVE avg alpha 5d |
|---|---:|---:|---:|---:|---:|---:|
| Best unfiltered 10-set row | 68 | -0.56 | 33.8 | 41 | 36.6 | -2.45 |
| RS band `2.4..6.7` best 10-set row | 10 | -0.01 | 60.0 | 8 | 62.5 | 0.88 |

Feature-bucket analysis showed `relative_strength_vs_benchmark_3m` is predictive in the smoke sample, but not monotonically:

| Feature | Regime | Best bucket | Spread | Read |
|---|---|---|---:|---|
| `relative_strength_vs_benchmark_3m` | all | Q3 `2.4-6.7` | 48.1pp | Moderate positive RS worked; very high RS failed. |
| `relative_strength_vs_benchmark_3m` | OFFENSIVE | Q3 `3.9-6.7` | 54.8pp | Best OFFENSIVE 5d win rate and positive average alpha, but small sample. |

### Decision

Do not promote a live TI RS filter yet. The RS band is the first promising TI rehabilitation candidate, but the filtered smoke has only `8-13` OFFENSIVE signals per top row and needs a full-grid or rolling validation before any live filter or reference-only decision.

Next TI research step: run full-grid or rolling G2 validation for a bounded RS filter, starting with `relative_strength_vs_benchmark_3m:2.4..6.7` and inspecting an OFFENSIVE-focused cut such as `3.9..6.7`.

## 2026-05-08 - MB G1 feature-bucket analysis

### Setup

- Scanner: `momentum_burst`
- Regime: `OFFENSIVE`
- Input: `data/calibration/2026-04-23-momentum_burst-NIFTY500-signals.csv`
- Signals Analysed: 16232

### Results

The feature bucket analysis successfully identified several highly predictive features exceeding the 15pp win-rate spread promotion threshold:

| Feature | Spread | Best Bucket | Win Rate | Read |
|---|---:|---|---:|---|
| `consolidation_days` | 60.2pp | `<4.0` | 72.5% | Very strong predictor; short consolidations work best. |
| `prior_10d_run_pct` | 60.0pp | `<-2.3` | 76.0% | MB prefers setups without massive prior 10d exhaustion runs. |
| `nr_count_10d` | 55.6pp | `>5.0` | 100.0% | Very high win rate but small `n=40` sub-sample at extreme quartiles. |
| `prior_20d_run_pct` | 47.4pp | `<-8.0` | 71.6% | Again, deep recent exhaustion prior to the setup burst performs better. |
| `distance_from_20d_high_pct`| 41.9pp| `<-2.2` | 70.2% | |

### Decision

Proceed to G2 Extended Calibration Validation for Momentum Burst using these top candidate features.

## 2026-05-08 - TI G1 feature-bucket analysis

### Setup

- Scanner: `trend_intensity`
- Regime: `OFFENSIVE`
- Input: `data/calibration/2026-04-24-trend_intensity-NIFTY500-signals.csv`
- Signals Analysed: 1416

### Results

| Feature | Spread | Best Bucket | Win Rate | Read |
|---|---:|---|---:|---|
| `trend_efficiency_ratio` | 45.2pp | `<0.3` | 52.8% | High spread. Very dense or straight-line trends (>0.5) perform very poorly (7.6% win rate). |
| `pullback_depth_20d` | 42.4pp | `<16.0` | 50.1% | Shallow pullbacks perform much better than deep flush pullbacks. |
| `distance_above_ma50_pct` | 34.6pp | `<11.1` | 49.7% | Setups closer to the MA50 are significantly better (50% vs <20%). |
| `vol_dryup_ratio_10d` | 33.8pp | `<1.0` | 47.2% | Very tight volume prior to breakout favors the setup. |

### Decision

Next TI research step: run full-grid or rolling G2 validation for a bounded RS filter, starting with `relative_strength_vs_benchmark_3m:2.4..6.7` and inspecting an OFFENSIVE-focused cut such as `3.9..6.7`.

## 2026-05-08 - MB & TI G2 Extended Calibration Validation

### Overview
Conducted comprehensive Grid Validation (G2) across all standard parameters over a 6-month historical window (2025-01-01 to 2025-06-30) for the top G1 candidate features:
- **MB Candidates:** `consolidation_days < 4.0`, `prior_10d_run_pct < -2.3`
- **TI Candidates:** `trend_efficiency_ratio < 0.3`, `pullback_depth_20d < 16.0`

### Results

#### Momentum Burst
1. **`consolidation_days < 4.0`:** **FAILED.** Dropped the 5d win rate to ~40-44% across grid arrays. The very high hit rate in G1 was an artifact of the single day cross-section and did not generalize over a wider temporal horizon.
2. **`prior_10d_run_pct < -2.3`:** **VALIDATED.** Consistently delivered `win_rate_5d > 50%` and pushed `offensive_win_rate_5d > 60%` across the top 20 parameter buckets, while shrinking raw signal bloat safely.

#### Trend Intensity
1. **`trend_efficiency_ratio < 0.3`:** **FAILED.** Marginal win-rate improvement (~51%) but defensive regimes completely failed, and offensive alpha remained poor (-0.76%).
2. **`pullback_depth_20d < 16.0`:** **VALIDATED.** Yielded solid stability improvements: `win_rate_5d` normalized to ~50.6% and importantly `offensive_win_rate_5d` climbed to > 50% with significantly mitigated (nearly flat) median alpha.

### Decision (G3 Promotion)
- **MB G3 Promotion:** Add `PRIOR_10D_RUN_MAX_PCT = -2.3` as a live quality filter.
- **TI G3 Promotion:** Add `TI_PULLBACK_DEPTH_MAX_PCT = 16.0` as a live quality filter.

## 2026-05-08 - TI RS-band full-grid calibration validation

### Setup

- Scanner: `trend_intensity`
- Universe: `NIFTY500`
- Window: `2025-01-01` to `2025-06-30` (2025-H1)
- Feature filter: `relative_strength_vs_benchmark_3m:2.4..6.7`
- Outputs: `data/calibration/rs-band-full-summary.csv`

### Results

The bounded Relative Strength filter (`2.4 - 6.7`) completely choked the signal count when subjected to the full grid space across the entire H1 window. 
The top parameter sets returned highly constrained signal counts (e.g., `n_signals: 6-12` over 6 months), though they did achieve borderline offensive win rates near ~60%. Parameter sets with higher signal counts (n > 40) immediately reverted to weak baseline properties (`offensive_win_rate_5d < 40%`, negative `offensive_avg_alpha_5d`).

### Decision

**FAILED.** Do not promote a live TI RS filter. The RS band fails to generalize beyond the smoke validation sample. It heavily restricts signal count without fundamentally resolving the negative alpha property of the Trend Intensity setup.
\ n # #   2 0 2 6 - 0 5 - 1 6   -   S t r e a m   G   T a s k   9 :   S c a n n e r   D e m o t i o n   R e v i e w \ n \ n # # #   O v e r v i e w \ n F o l l o w i n g   t h e   c o m p l e t i o n   o f   t h e   S t r e a m   G   f e a t u r e   a n a l y s i s   p i p e l i n e   a n d   G 2   e x t e n d e d   v a l i d a t i o n ,   a   f o r m a l   d e c i s i o n   i s   r e q u i r e d   r e g a r d i n g   t h e   l i v e   t r a d i n g   s t a t u s   o f   t h e   M o m e n t u m   B u r s t   a n d   T r e n d   I n t e n s i t y   s c a n n e r s . \ n \ n # # #   M o m e n t u m   B u r s t   ( M B )   D e c i s i o n :   * * R E T A I N   ( A C T I V E ) * * \ n -   * * R a t i o n a l e : * *   T h e   p r o m o t i o n   o f   t h e   \ p r i o r _ 1 0 d _ r u n _ p c t   <   - 2 . 3 \   f i l t e r   s u c c e s s f u l l y   r e h a b i l i t a t e d   t h e   s e t u p .   \ n -   * * M e t r i c s : * *   I t   p u s h e d   t h e   O F F E N S I V E   5 d   w i n   r a t e   a b o v e   6 0 %   d u r i n g   t h e   G 2   v a l i d a t i o n   w i n d o w ,   r e t u r n i n g   t h e   s c a n n e r   t o   a   v i a b l e   e d g e . \ n -   * * A c t i o n : * *   M B   r e m a i n s   a   f u l l y   a c t i v e ,   t r a d a b l e   s c a n n e r . \ n \ n # # #   T r e n d   I n t e n s i t y   ( T I )   D e c i s i o n :   * * D E M O T E D   ( R E F E R E N C E _ O N L Y ) * * \ n -   * * R a t i o n a l e : * *   W h i l e   t h e   \ p u l l b a c k _ d e p t h _ 2 0 d   <   1 6 . 0 \   f i l t e r   s u c c e s s f u l l y   p u s h e d   t h e   5 d   w i n   r a t e   s l i g h t l y   a b o v e   5 0 % ,   t h e   s e t u p   c o n t i n u e s   t o   p r i n t   s t r u c t u r a l l y   f l a t   o r   n e g a t i v e   a l p h a .   T h e   R S - b a n d   v a l i d a t i o n   a l s o   f a i l e d   t o   r e s o l v e   t h i s   n e g a t i v e   a l p h a   p r o p e r t y   w i t h o u t   c h o k i n g   s i g n a l   c o u n t s   t o   n e a r - z e r o . \ n -   * * M e t r i c s : * *   O F F E N S I V E   a v g   a l p h a   r e m a i n s   f l a t / n e g a t i v e . \ n -   * * A c t i o n : * *   T I   i s   f o r m a l l y   d e m o t e d   t o   \ R E F E R E N C E _ O N L Y \   s t a t u s .   I t   w i l l   r e m a i n   i n   t h e   d a i l y   r u n s   t o   p r o v i d e   m a r k e t   s t r u c t u r e   c o n t e x t ,   b u t   n o   p a p e r   o r   r e a l   c a p i t a l   s h o u l d   b e   a l l o c a t e d   t o   t h e s e   s e t u p s   u n t i l   a   s t r u c t u r a l   f i x   i s   f o u n d .  
 