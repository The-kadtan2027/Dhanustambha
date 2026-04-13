# Architecture Decision Records (ADRs)

> These records explain *why* decisions were made. Before changing any of these decisions, read the rationale. If you disagree with a decision, document it here with a new ADR rather than silently changing things.

---

## ADR-001 — Python over Java for this project

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** The primary developer (Gaju) is a senior Java/JBoss architect by profession. The question was whether to use Java or Python.

**Decision:** Python.

**Rationale:**
- Every meaningful Indian market data library (`nsepy`, `jugaad-trader`, `nsetools`, Zerodha's `kiteconnect`) is Python-first. Java equivalents are unmaintained or nonexistent.
- `pandas`, `numpy`, `ta-lib` make OHLCV analysis and indicator calculation idiomatic. Replicating this in Java would require building from scratch.
- For EOD swing trading (daily batch, not HFT), Python's performance is more than sufficient.
- FastAPI gives a production-quality REST API layer with zero boilerplate.
- Runs natively on WSL2 and Termux with minimal overhead.

**Consequence:** Java skills are not used in this project. That's fine — this is a different domain tool, not an enterprise application.

---

## ADR-002 — SQLite over PostgreSQL or MySQL

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** Needed a persistent data store for OHLCV data (~500 symbols × 252 trading days/year × 5+ years = ~630,000 rows). Options: SQLite, PostgreSQL, MySQL, flat CSV files.

**Decision:** SQLite.

**Rationale:**
- Zero infrastructure. No server process, no port, no auth config.
- Runs identically on WSL2 and Termux — same file, same queries.
- 630,000 rows is small for SQLite. It handles tens of millions of rows without issue at EOD-batch read patterns.
- The entire DB is a single `.db` file — trivial to back up (`cp market.db market.db.bak`).
- `pandas` reads directly from SQLite via `pd.read_sql()` — the integration is first-class.

**When to revisit:** If we add intraday data (1-minute bars × 375 minutes × 500 symbols × 252 days = ~47 million rows/year), SQLite will become a bottleneck. Switch to TimescaleDB (PostgreSQL extension) at that point.

---

## ADR-003 — Free NSE data first, Zerodha Kite later

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** Zerodha Kite Connect API provides clean, reliable historical data but requires a ₹2000/month subscription fee. NSE Bhavcopy and `nsepy`/`yfinance` are free.

**Decision:** Free data first. Design the `fetcher.py` interface so switching to Kite requires only changing the implementation, not the interface.

**Rationale:**
- Phase 1 is about validating the system, not committing money to subscriptions.
- The `fetch_ohlcv(symbols, date)` interface is data-source agnostic. Swapping the backend is a one-file change.
- NSE Bhavcopy (official daily CSV) is the authoritative source — it's what Kite's data is derived from anyway.

**Known limitations of free data:**
- `nsepy` is sometimes unstable / unmaintained. Have `yfinance` as fallback.
- `yfinance` appends `.NS` to symbols — the store layer must strip this before writing to DB.
- Neither source provides adjusted prices for corporate actions. Backtests on historical data must flag this caveat.

---

## ADR-004 — EOD (End of Day) data only; no intraday

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** Should the system use intraday (1-minute or 5-minute) data for better entry timing?

**Decision:** EOD only for all phases through Phase 3.

**Rationale:**
- Pradeep Bonde's methodology is explicitly EOD-based. He scans after market close, builds a watchlist, and enters the next morning near the open. This eliminates the need for intraday data entirely.
- Intraday data requires a paid subscription and adds significant storage complexity.
- This keeps the system runnable on homelab hardware with a once-daily cron job.
- The trader places orders manually the next morning — intraday data doesn't help this workflow.

---

## ADR-005 — No automated order execution (ever, in this phase)

**Date:** 2026-04-11  
**Status:** Accepted — permanent for Phase 1-3

**Context:** Should the system automatically place buy/sell orders when a setup triggers?

**Decision:** No. Hard no. All execution is manual.

**Rationale:**
- The primary goal is learning. Automated execution would bypass the learning feedback loop.
- A bug in the scanner or position sizer could place incorrect orders and cause real financial loss.
- SEBI and broker terms of service have specific rules around automated trading that require different licensing/registration.
- The psychological element of trading — discipline, patience — cannot be learned if a machine executes for you.

**Future:** If we ever want automated execution, it will be a completely separate project with its own safety systems, paper-trading validation period, and explicit legal review.

---

## ADR-006 — NIFTY 500 as primary universe

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** NSE has ~2000 listed stocks. Should we scan all of them?

**Decision:** NIFTY 500 as the default universe for Phase 1.

**Rationale:**
- NIFTY 500 covers ~95% of total NSE market cap. The best momentum setups are almost always in this universe.
- Penny stocks and illiquid small-caps in the NSE Total Market universe produce false positives in momentum scanners and are dangerous to trade (wide bid-ask spreads, easy to manipulate).
- 500 symbols × 5 years = ~630,000 rows. Manageable on SQLite, fast to scan.
- The minimum liquidity filter (20-day average volume > 200,000 shares) naturally excludes most junk stocks anyway.

**Expansion path:** Once Phase 1 is stable, extend to NIFTY 1000 or add a mid-cap sub-scan separately.

---

## ADR-007 — Market Monitor thresholds need NSE calibration

**Date:** 2026-04-11  
**Status:** Open / Needs validation

**Context:** Pradeep Bonde's Market Monitor thresholds (% above MA20 > 55% = Offensive, etc.) were calibrated on US markets (S&P 500 universe). NSE may behave differently.

**Decision:** Use Pradeep's thresholds as starting point. Mark all thresholds as explicitly configurable in `config.py`. After Phase 1 is running, back-test the thresholds against 3 years of NSE breadth data and adjust.

**Action item:** After Phase 1, generate historical breadth data and compare the Offensive/Defensive verdicts against actual NIFTY 500 returns in the following week. Tune thresholds to maximize signal quality.

---

## ADR-008 — cron over a persistent scheduler (APScheduler, Celery)

**Date:** 2026-04-11  
**Status:** Accepted

**Context:** Should we use a Python-native scheduler like APScheduler, or rely on OS-level cron?

**Decision:** OS cron (WSL2 cron) and Termux:Boot/cron.

**Rationale:**
- No persistent process to manage. No memory leak risk. No recovery logic needed.
- If the laptop is off at 16:30, the job doesn't run — that's acceptable. The trader will notice and run manually.
- `cron` is universal, understood, and battle-tested.
- A persistent scheduler adds complexity for no benefit in this use case.

**Cron entry (WSL2):**
```cron
30 16 * * 1-5 cd /home/gaju/dhanustambha && python scripts/daily_briefing.py >> logs/briefing.log 2>&1
```

**Termux equivalent:**
```bash
# In ~/.termux/boot/start-services.sh
crond
```
