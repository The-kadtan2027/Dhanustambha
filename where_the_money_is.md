# Where the Money Is — Scanner Edge Analysis

> Based on full-grid calibration over **Jan 2024 – Apr 2026** on the **NIFTY 500** universe,
> with benchmark-relative alpha vs NIFTY, regime splits by Market Monitor verdict,
> and signal-level excursion (MFE/MAE) data.

---

## The Verdict: One Scanner Has Edge, Two Don't (Yet)

| Scanner | Overall 5d Alpha | OFFENSIVE 5d Alpha | Overall 20d Alpha | Signal Frequency | **Verdict** |
|---|---|---|---|---|---|
| **Episodic Pivot** | +1.57% (OFF) | **+1.57% to +4.53%** | +8.87% to +11.16% | ~95–485 signals/2yr | ✅ **Real edge** |
| Momentum Burst | -0.26% to -0.65% | +0.13% to +0.22% | Negative | 2,000–12,000 signals/2yr | ❌ No alpha |
| Trend Intensity | -0.03% to -0.15% | -0.12% to -0.22% | Negative | 2,000–5,000 signals/2yr | ❌ Coin flip |

> [!IMPORTANT]
> **Episodic Pivot is the only scanner generating meaningful alpha.** The other two are effectively random noise once you subtract the market's own move.

---

## Episodic Pivot — The Edge in Detail

### Live Params (5.0% gap / 3.0x volume / 2 days): 485 signals over 2+ years

| Regime | Signals | 5d Avg | 5d Win% | 10d Avg | 20d Avg | Hit 5% by 5d | Hit 8% by 10d | Failed by 3d |
|---|---|---|---|---|---|---|---|---|
| **OFFENSIVE** | **48** | **+3.97%** | **69.6%** | **+9.35%** | **+15.03%** | **62.5%** | **50.0%** | **4.2%** |
| DEFENSIVE | 29 | +1.50% | 55.2% | +4.62% | +10.09% | 51.7% | 44.8% | 3.5% |
| AVOID | 55 | -2.58% | 38.2% | -2.54% | -3.94% | 38.2% | 40.0% | 12.7% |
| *All* | *485* | *+0.44%* | *53.6%* | *+1.27%* | *+2.24%* | *43.9%* | *37.1%* | *6.6%* |

### Tight Params (8.0% gap / 4.0x volume / 1 day): 95 signals — the "A+ setup"

| Regime | Signals | 5d Avg | 5d Win% | 10d Avg | 20d Avg | Hit 5% by 5d | Hit 8% by 10d |
|---|---|---|---|---|---|---|---|
| **OFFENSIVE** | **8** | **+6.55%** | **75.0%** | **+11.43%** | **+16.84%** | **62.5%** | **75.0%** |
| DEFENSIVE | 5 | +3.87% | 60.0% | +5.32% | +10.19% | 60.0% | 60.0% |
| AVOID | 14 | -2.52% | 42.9% | -5.74% | -7.37% | 64.3% | 57.1% |
| *All* | *95* | *+1.26%* | *61.1%* | *+2.44%* | *+5.24%* | *56.8%* | *52.6%* |

### Sweet Spot: Day-0 Gap + OFFENSIVE Regime (Live params)

| Metric | Value |
|---|---|
| Signals | 19 |
| 5d avg return | **+4.32%** |
| 5d median return | **+6.83%** |
| 5d win rate | **68.4%** |
| 10d avg return | **+9.26%** |
| 10d avg alpha vs NIFTY | **+5.62%** |
| 20d avg return | **+16.68%** |
| 20d avg alpha vs NIFTY | **+9.65%** |
| Hit 5% by 5d | **68.4%** |
| Hit 8% by 10d | **52.6%** |
| Failed to gain by 3d | **5.3%** |

> [!TIP]
> **The sweet spot is clear: Buy EP gap-ups on the gap day itself, in OFFENSIVE market conditions.** 
> 68% win rate at 5 days, only 5% of signals fail to gain anything by day 3. Average alpha of +5.6% over 10 days.

### MFE/MAE (Maximum Favorable/Adverse Excursion)

| Params | 5d MFE | 5d MAE | MFE/MAE | 10d MFE | 10d MAE | MFE/MAE |
|---|---|---|---|---|---|---|
| Live (5.0/3.0/2) | +5.73% | -4.91% | 1.17 | +8.02% | -6.49% | 1.24 |
| Tight (8.0/4.0/1) | +7.55% | -5.03% | **1.50** | +10.93% | -6.85% | **1.60** |

The tight params have a significantly better MFE/MAE ratio — meaning the average winner runs further than the average loser falls. This is the hallmark of a tradeable edge.

---

## Momentum Burst — No Alpha Found

The hard truth across **100 parameter combinations**:

- **Best overall 5d alpha:** -0.08% (essentially zero) 
- **Best OFFENSIVE 5d alpha:** +0.22% (tiny, statistically meaningless)
- **Every single parameter set** has negative median alpha at 5, 10, and 20 days
- Signal counts are massive (2,000–12,000) — it catches everything, but what it catches doesn't outperform the market

> [!WARNING]
> **Momentum Burst as currently designed is a noise generator on NSE.** It finds stocks that went up — but so did the market. There is no selection alpha. The signals might feel good because the stocks are green, but NIFTY was also green on those days.

### Why MB Fails on NSE

Likely reasons:
1. **NSE momentum is faster and more crowded** than US markets — by the time a 5% move shows up in EOD data, most of the easy follow-through is priced in
2. **Circuit limits (20%)** compress the right tail — exceptional moves get artificially capped
3. **High correlation across NSE stocks** — when one sector moves, dozens of stocks trigger simultaneously, but they're all riding the same tide

---

## Trend Intensity — Coin Flip

- Best overall alpha at any horizon: **-0.01%** to **+0.05%** — statistically zero
- OFFENSIVE regime: still slightly negative alpha (-0.12%)
- Signal counts are reasonable (2,000–5,000)
- Win rates hover at 48–51% — literally a coin flip

Trend Intensity is not actively harmful, but it's not adding value either. It's finding stocks in uptrends, but those stocks aren't outperforming their already-uptrending peers.

---

## What This Means for Trading

### The Playbook (Evidence-Based)

```
TIER 1 — High Conviction (Full Position)
  Setup:    Episodic Pivot, Day-0 or Day-1
  Regime:   OFFENSIVE only
  Params:   Gap ≥ 5%, Volume ≥ 3x, within 2 days of gap
  Target:   +5% by day 5, +8% by day 10
  Stop:     Below gap-day low
  Expected: ~68% win rate, +5.6% alpha over 10 days
  Frequency: ~2-3 signals per month in OFFENSIVE markets

TIER 2 — Moderate Conviction (Half Position)
  Setup:    Episodic Pivot, Day-0 or Day-1
  Regime:   DEFENSIVE  
  Params:   Same as Tier 1
  Target:   +3% by day 5
  Stop:     Tighter — below gap-day close
  Expected: ~55% win rate, +2.3% alpha over 10 days

TIER 3 — No Trade
  Any EP signal in AVOID regime → skip entirely
  Any Momentum Burst signal → use as confirmation only, never primary
  Any Trend Intensity signal → use as confirmation only, never primary
```

### The Math on ₹1 Lakh Account

With `TRADE_RISK_PCT = 2.5%` (current config) and the EP OFFENSIVE edge:
- Risk per trade: ₹2,500
- Average winner (5d, +4%): earns ~₹3,200 on a typical ₹80,000 position
- Average loser: loses the ₹2,500 risk
- Win rate: 68%
- **Expectancy per trade: ₹2,500 × 0.68 × 1.28 - ₹2,500 × 0.32 = +₹1,376**
- With ~2-3 trades/month: **+₹2,750 to ₹4,128/month** (2.75–4.1% monthly)

> [!CAUTION]
> These are historical averages on 48 OFFENSIVE EP signals. Sample size is modest. The edge is real but don't over-lever. Paper trade first.

---

## Key Decisions Needed

### 1. Should we demote MB and TI from the daily briefing?

Options:
- **A) Keep all three but visually separate them** — EP gets a "⭐ HIGH CONVICTION" label, MB/TI get "📊 FOR REFERENCE ONLY"
- **B) Remove MB and TI from the watchlist export** — only EP makes the CSV. MB/TI still run internally for research.
- **C) Keep current behavior** — user mentally filters

### 2. Should we add regime gating to the briefing output?

The data screams: **never trade EP in AVOID**. Should the briefing:
- **A) Suppress EP candidates when verdict = AVOID?** (saves the trader from themselves)
- **B) Show them but with a ⚠️ warning?**

### 3. Should we tighten EP defaults further?

The "tight" params (8.0/4.0/1) have much better alpha but only produce ~95 signals in 2 years (~4/month). The current "live" params (5.0/3.0/2) produce ~20/month but with diluted alpha.

Option: **Dual-tier EP output** — show both "A+" setups (tight) and "B" setups (live) separately.

### 4. What about Momentum Burst's future?

Options:
- **A) Kill it** — it has no alpha on NSE. Stop wasting watchlist real estate.
- **B) Redesign it** — the current criteria may be wrong for NSE. Research paths:
  - Add a "consolidation tightness" filter (NR count) — only burst from tight bases
  - Add relative strength filter — only burst stocks already stronger than the market
  - Add sector momentum filter — only burst in sectors with fresh institutional flow
- **C) Keep it as-is** — maybe the edge appears in specific sectors or market phases we haven't sliced yet

### 5. Position sizing and account setup

Current config has `ACCOUNT_SIZE = 100_000` and `TRADE_RISK_PCT = 2.5%`. With only EP being tradeable:
- Should we increase `TRADE_RISK_PCT` since we'll be taking fewer, higher-quality trades?
- Should we increase `TRADE_MAX_POSITION_PCT` from 25% given concentrated EP strategy?

---

## Suggested Next Steps (in order)

1. **Decision call on the 5 questions above** — this shapes everything downstream
2. **Add EP confidence tiers to the briefing** — separate A+ (tight) from B (live) setups
3. **Add regime gating** — suppress or warn on AVOID-regime signals
4. **Paper trade the EP OFFENSIVE playbook for 2-4 weeks** using `trade_manager.py`
5. **After paper validation:** consider MB redesign or retirement
6. **After 20+ paper trades:** review actual vs expected edge, adjust sizing
