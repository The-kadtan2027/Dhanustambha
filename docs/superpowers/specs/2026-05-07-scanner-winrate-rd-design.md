# Stream G — Scanner Win-Rate R&D Design

**Date:** 2026-05-07  
**Author:** Gaju (via brainstorming session)  
**Status:** Completed — feature pipelines integrated and live filters promoted

---

## Background

Stream D (research-grade calibration) produced rich signal-level output with feature columns
per trade but never sliced those features against outcomes to find what actually predicts
success. `where_the_money_is.md` established the ground truth:

- **Episodic Pivot** is the only scanner with real alpha (+5.6% vs NIFTY over 10d, OFFENSIVE)
- **Momentum Burst** and **Trend Intensity** generate noise-level alpha (-0.03% to -0.65%)
- The EP A+ tier (gap ≥ 8%, vol ≥ 4x, day-0) is better (75% win rate) but tiny signal count

The goal of this stream is to answer: **what features of an EP signal best predict whether
it will be a winner?** Then apply the same analysis to MB and TI to either rehabilitate them
or retire them from the live watchlist.

---

## Goals

1. Build a feature bucket analysis script to identify predictive signal characteristics
2. Validate top features via extended calibration grid
3. Promote validated features to live scanner filters
4. Apply the same pipeline to MB and TI

---

## Non-Goals

- No intraday data, no broker integration
- No ML models — keep analysis interpretable and sample-size-safe
- No change to the daily briefing orchestration workflow
- No regressions to the existing 76-test suite baseline

---

## Approach: Analysis → Validation → Promotion (Sequenced)

```
Phase G1: Feature Bucket Analysis
  scripts/analyze_signal_features.py (NEW)
  Input:  signals CSV from data/calibration/
  Output: ranked feature table + data/research/{date}-{scanner}-feature-analysis.md

Phase G2: Extended Calibration Validation  
  scripts/calibrate_thresholds.py (MODIFY)
  Input:  top 2–3 features from G1 with spread > 15pp win rate
  Output: summary + signals CSV with feature filter dims added

Phase G3: Live Filter Promotion
  src/scanner/episodic_pivot.py + config.py (MODIFY)
  Gate:   G1 spread > 15pp AND G2 median_alpha_5d improvement AND
          OFFENSIVE signal count stays ≥ 10/month

Phase G4: MB/TI Rehabilitation (same pipeline, after EP)
  scripts/analyze_signal_features.py re-used on MB/TI signals
  MB focus: mb_quality=HIGH vs STANDARD alpha split
  TI focus: relative_strength_vs_benchmark_3m as new feature
```

---

## Phase G1 — Feature Analysis Script

### What it does

For each feature column in a signals CSV:

- **Numeric columns** (gap_close_location_pct, prior_65d_run_pct, gap_fill_pct, etc.):
  Split into 4 quantile buckets. Compute per bucket:
  `N, 5d_win_rate, 10d_win_rate, 5d_avg_alpha, 10d_avg_alpha, avg_mfe_mae_ratio`

- **Boolean columns** (is_first_gap_in_6m):
  Split True/False. Same metrics.

- **Categorical features** (market_verdict):
  Already known from where_the_money_is.md but included for completeness.

### Feature ranking

Sort features by **win-rate spread** = best bucket win rate − worst bucket win rate.

Promotion candidates: spread ≥ 15pp **and** N ≥ 15 in each bucket.  
No-signal: spread < 5pp → label "no predictive value" in output.

### CLI interface

```bash
python scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \
  --scanner episodic_pivot \
  --regime OFFENSIVE          # optional: all | OFFENSIVE | DEFENSIVE
```

### Outputs

1. Console: ranked feature table (top 10 by spread)
2. `data/research/YYYY-MM-DD-{scanner}-feature-analysis.md` — full readable report

---

## Phase G2 — Extended Calibration Grid

After G1 identifies candidate features, `calibrate_thresholds.py` gains a `--feature-filters`
flag. Each feature filter is a discrete grid dimension added to the existing scan:

```bash
python scripts/calibrate_thresholds.py \
  --scanner episodic_pivot \
  --universe NIFTY500 \
  --feature-filters gap_close_location_pct:50,60,70 is_first_gap_in_6m:True,False
```

Grid grows ~6x per dimension. Add dims **one at a time** to control compute time.

Outputs use the existing `-summary.csv` and `-signals.csv` format, ranked by `median_alpha_5d`.

---

## Phase G3 — Live Filter Promotion Rules

A feature is promoted only when **all three gates pass**:

| Gate | Criterion |
|---|---|
| G1 significance | Win-rate spread ≥ 15pp, N ≥ 15 per bucket |
| G2 alpha improvement | Extended calibration `median_alpha_5d` improves vs baseline |
| Signal count floor | OFFENSIVE signals in calibration window stay ≥ 5 total (avoids filters so tight they produce no live signals) |

When promoted:
- Add `EP_MIN_GAP_CLOSE_LOCATION_PCT = 60.0` (example) to `config.py`
- Update `detect_episodic_pivot()` to apply the filter
- Add targeted unit test with synthetic data confirming the filter applies

---

## Phase G4 — MB/TI Rehabilitation

### Momentum Burst

Primary hypothesis: MB HIGH quality setups (NR_10 ≥ 6, close_location ≥ 70%,
20d_high_breakout) have genuine alpha that is diluted by the STANDARD majority.

Research action:
1. Run `analyze_signal_features.py` on MB signals CSV
2. Slice by `mb_quality` first — if HIGH has > 15pp better win rate, the fix is to make
   all three HIGH criteria mandatory detection conditions (not just labels)
3. Validate with G2 extended calibration

If HIGH criteria don't help: MB is demoted to **reference-only** in the daily briefing — it continues running and appears in a separate "For Reference" section below the main watchlist, but is never promoted to the top-N watchlist CSV. No live trades on MB signals until further evidence.

### Trend Intensity

Primary hypothesis: TI works for stocks already outperforming the market.

Research action:
1. Add `relative_strength_vs_benchmark_3m` feature to `prepare_trend_intensity_features()` (already planned in Stream D feature list)
2. Run `analyze_signal_features.py` on TI signals sliced by RS quantile
3. If top-RS-quartile TI signals show alpha > 1%, validate and promote

If RS doesn't help: TI is demoted to **reference-only** in the daily briefing using the same mechanic as MB above.

---

## Files Changed

| File | Change |
|---|---|
| `scripts/analyze_signal_features.py` | **NEW** — core feature bucket analysis |
| `scripts/calibrate_thresholds.py` | **MODIFY** — add `--feature-filters` argument |
| `src/scanner/episodic_pivot.py` | **MODIFY** — add promoted live filter(s) |
| `src/scanner/momentum_burst.py` | **MODIFY** — optionally harden HIGH to detection criteria |
| `src/scanner/trend_intensity.py` | **MODIFY** — add RS filter if validated |
| `config.py` | **MODIFY** — new constants for promoted feature thresholds |
| `tests/test_scanner.py` | **MODIFY** — tests for new live filter logic |
| `data/research/` | **NEW dir** — markdown research reports from G1 runs |

---

## Verification Plan

### G1 (Feature Analysis)

```bash
# Smoke test: run on existing signals CSV and verify output shape
python scripts/analyze_signal_features.py \
  --signals data/calibration/2026-04-25-episodic_pivot-NIFTY500-signals.csv \
  --scanner episodic_pivot --regime OFFENSIVE

# Confirm output file created
dir data\research\
```

### G2 (Extended Calibration)

```bash
# Add one feature dim to EP grid, fast run to confirm mechanics
python scripts/calibrate_thresholds.py --scanner episodic_pivot \
  --universe NIFTY500 --max-param-sets 10 \
  --feature-filters gap_close_location_pct:50,70
```

### G3 (Live Filter Promotion)

```bash
# Full test suite must still pass after any scanner change
pytest tests/ -v
# Confirm signal count is acceptable
python scripts/daily_briefing.py --date 2026-04-16
```

---

## Success Criteria

- At least one EP feature shows ≥ 15pp win-rate spread and passes all three promotion gates
- After promotion, EP OFFENSIVE win rate in calibration data improves from current 68–75% baseline
- MB HIGH vs STANDARD slice confirms or refutes the quality tier hypothesis with evidence
- All existing tests continue to pass throughout

---

## Open Questions

None. All design decisions are resolved.

---

## Sequencing

```
Week 1:  G1 — build analyze_signal_features.py, run on EP signals [COMPLETED]
Week 2:  G1 findings review → pick top 2 EP features for G2 [COMPLETED]
Week 3:  G2 — extended EP calibration with feature dims [COMPLETED]
Week 4:  G3 — promote validated EP features to live filters [COMPLETED]
Week 5:  G4 — MB/TI feature analysis and rehabilitation decision [COMPLETED — MB prior_run and TI pullback_depth promoted]
```
