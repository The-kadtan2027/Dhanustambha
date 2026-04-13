# Stockbee Methodology — Adapted for NSE/BSE

> Source: Pradeep Bonde (Stockbee) — https://stockbee.blogspot.com/p/methods-and-philosphy.html  
> Adaptation: Translated from US market context to Indian NSE/BSE market context  
> This document is the trading bible for this system. All scanner logic derives from it.

---

## Core Philosophy

1. **Stocks move in short-term momentum bursts.** Not slowly, not linearly — in explosive bursts of 3–10 days driven by a catalyst. The goal is to be positioned at the start of these bursts.
2. **Methods trump markets.** A good method applied consistently beats a genius who improvises. Build a system and follow it.
3. **Market condition first.** Trading against a weak market destroys profits. Check the Market Monitor every day before looking at a single stock.
4. **Process > outcome (short-term).** A losing trade that followed the rules is a good trade. A winning trade that broke the rules is a bad trade.
5. **Study past winners.** Every weekend, look at what worked. Look at the chart *before* the big move. Train your eye to recognize the setup earlier.

---

## The Three Setups

### 1. Momentum Burst (MB)

**The idea:** A stock that has been quiet suddenly explodes in price and volume in 1–3 days. This is institutional or informed buying. The first burst is often followed by more buying over the next 5–15 days.

**What it looks like on a chart:**
- Stock consolidating in a tight range for days/weeks
- Sudden single-bar (or 2-bar) move of 5–20%+ on 2–5x normal volume
- Often on a sector catalyst, earnings, management change, or broader market move

**Entry:** Buy as early in the burst as possible. Ideally within the first 1–2 days of the move. Late entries have poor risk/reward.

**Exit:** 
- **Stop:** Below the low of the burst candle (or 2-candle formation). If the stock gives back the burst, the thesis is wrong.
- **Target:** 10–20% from entry, or 2–3 weeks — whichever comes first. These are short-term trades.
- **Trailing stop:** After a 10%+ gain, trail with MA5 or recent swing low.

**NSE specifics:**
- Upper circuit stocks (5% or 10% circuit) can show artificial momentum. Check if the stock hit a circuit. If yes, skip.
- NSE has many operator-driven stocks in small/midcap. Volume filter (min 200,000 avg volume) removes most of these.

---

### 2. Episodic Pivot (EP)

**The idea:** A significant corporate event (earnings beat, major order, management change, sector tailwind) structurally resets the stock's trading range. The stock gaps up significantly and *stays up*. This is different from a dead-cat bounce — the holding of the gap proves genuine institutional interest.

**What it looks like on a chart:**
- Stock in a flat or downtrending range for months
- A large gap up (4–10%+) on 3–5x normal volume on a specific news day
- Stock holds above the gap for days/weeks, building a new base

**Entry:** Ideally within 0–5 trading days of the gap. Buy when the stock consolidates near the gap level (not chasing it 15% above the gap).

**Exit:**
- **Stop:** Below the gap-open price. If the gap is filled, the thesis is invalidated.
- **Target:** These trades can run 20–50%+ over weeks. Use a wider stop and longer time horizon than Momentum Burst.
- Use a weekly chart to manage EP trades — don't get shaken out by daily noise.

**NSE specifics:**
- Earnings season in India: January-February (Q3), April-May (Q4/Annual), July-August (Q1), October-November (Q2)
- Corporate actions (rights issues, buybacks, demergers) also create EPs
- NSE Announcements page: `https://www.nseindia.com/companies-listing/corporate-filings-announcements` — the trigger source for EPs

---

### 3. Trend Intensity Breakout (TI)

**The idea:** Some stocks move up steadily, quietly, consistently — week after week — without big swings. These are the multi-month leaders. When they break to new highs on above-average volume, it signals the trend is accelerating.

**What it looks like on a chart:**
- Stock above MA50 consistently for 3–6 months
- MA50 is rising steadily
- Relatively low ATR (not volatile)
- A new 10-week high breakout with above-average volume

**Entry:** Buy the breakout to new 10-week highs. These can also be bought on pullbacks to MA20 within the uptrend.

**Exit:**
- **Stop:** A weekly close below MA50 is the end of the trend. Use this as the stop reference.
- **Target:** No fixed target. Trail with MA50 weekly. These can run for months.
- Accept some giveback — if you use a tight stop, you'll get shaken out. Position size smaller to allow for the volatility.

**NSE specifics:**
- FMCG, IT, and pharma sectors in India produce a disproportionate number of TI stocks
- Quality-focused indices (NIFTY Quality 50) are a good hunting ground for TI setups

---

## Market Monitor — Adapted for NSE

Pradeep's original Market Monitor uses TC2000 scans on S&P 500 stocks. We replicate the *concept* (market breadth) using our own SQLite/pandas calculations on NIFTY 500.

### Metrics and what they mean

**% stocks above MA20:**  
Short-term pulse. > 55% = broad participation = healthy for swing trading.  
< 45% = most stocks are below their 20-day average = weak internal structure.

**% stocks above MA50:**  
Medium-term trend. > 50% = majority in uptrends. If MA20% is high but MA50% is low, it's a relief rally in a downtrend — be cautious.

**New 52-week highs vs lows:**  
Directional strength. When highs >> lows (3:1 or better), the market is in expansion. When lows >> highs, distribution is happening even if the index is flat.

**Up-volume ratio:**  
Volume tells you conviction. > 60% of today's volume was in advancing stocks = institutions are buying. < 40% = they are selling.

**Advancing/Declining ratio:**  
Raw count. > 1.5 = broad breadth. < 0.8 = most stocks are declining regardless of index level.

### Verdict interpretation

**OFFENSIVE:** All systems go. Deploy capital. Use full position sizes. This is the time to find setups and trade them aggressively.

**DEFENSIVE:** Mixed signals. Reduce position sizes by 50%. Only trade A-quality setups (not B or C). Be quick to take profits. Do not add to existing positions.

**AVOID:** Capital preservation mode. No new trades. Hold cash. If you have open positions, tighten stops. The market is distributing.

---

## Daily Process Flow

This is the workflow the system automates (Phase 1), and the trader follows (all phases):

```
After 3:30 PM (market close)
    ↓
16:30 — daily_briefing.py runs automatically (cron)
    ↓
Market Monitor check
  → AVOID? → Print verdict, stop. No watchlist generated.
    ↓
Fetch today's OHLCV (already done by ingestion layer)
    ↓
Run 3 scanners in parallel
  → Momentum Burst scan
  → Episodic Pivot scan
  → Trend Intensity scan
    ↓
Merge, score, rank results
    ↓
Print and save watchlist (top 10 candidates)
    ↓
~17:00 — Trader reviews the watchlist
  → Looks at charts on Zerodha/TradingView for each candidate
  → Marks: "Will watch tomorrow morning" / "Skip"
  → Sets price alerts on broker app
    ↓
Next day 9:15 AM — Market opens
  → Trader watches only the pre-selected candidates
  → Enters if setup confirms (price action near entry point)
  → Places stop-loss order immediately after entry
    ↓
During the day — Let trades run
  → Only action: adjust stop if target partially met
    ↓
End of day — Review and log
  → Mark any closed trades in trade log
  → Note what worked and what didn't
```

---

## Risk Management Rules

These rules are non-negotiable. The system enforces them in the position sizer:

1. **Never risk more than 1% of account on a single trade.**  
   If you have ₹5,00,000: max risk per trade = ₹5,000.

2. **Never hold more than 5 open positions simultaneously.**  
   Focus forces better selection.

3. **Halve all position sizes in DEFENSIVE market conditions.**

4. **No new trades in AVOID conditions.** Hold cash. It is a position.

5. **Place the stop order on the same day you enter.** Never hold an unprotected position overnight.

6. **Cut losses quickly. The max loss on any trade is the planned stop.**  
   Do not hope. Do not average down. Take the stop and move on.

7. **Never trade a stock just because it's in the watchlist.** The watchlist is a candidate list. The setup must still be valid at your entry point next morning.
