# AGENT_RULES.md — Coding Agent Contract

> **Every coding agent working on this project must read and follow this file completely.**
> These rules exist because this project is built across many sessions by different agent instances with no shared memory. The rules prevent drift, broken assumptions, and wasted work.

---

## 1. Orientation Protocol (Every Session)

At the start of every session, before writing any code or making any decision:

```
1. Read README.md
2. Read docs/architecture/ARCHITECTURE.md
3. Read docs/architecture/DECISIONS.md
4. Read docs/plans/PROGRESS.md
5. Read the current active plan in docs/plans/
6. List any open questions you have BEFORE starting work
```

If you skip this step and start coding, you will likely contradict something already decided. Stop. Go back.

---

## 2. Scope Discipline

- **Work only the task assigned to you in the current plan.**
- Do not add features not in the plan. Do not refactor things you weren't asked to refactor.
- If you see something broken that is outside your current task, note it in a `# TODO:` comment and in `docs/plans/PROGRESS.md` under "Noted Issues". Do not fix it unless told to.
- If you notice the plan is wrong or incomplete, stop and ask. Do not improvise.

**The enemy of incremental progress is scope creep — even well-intentioned scope creep.**

---

## 3. File and Naming Conventions

### Python
- All source files live under `src/`. Match the module structure in `README.md` exactly.
- Tests live under `tests/`. Test file names mirror source file names: `src/monitor/breadth.py` → `tests/test_monitor_breadth.py`.
- Follow PEP 8. Max line length: 100 characters.
- All functions must have a docstring. No exceptions.
- Use type hints on all function signatures.

### Constants and configuration
- **Never hardcode thresholds, paths, or ticker lists inside source files.**
- All constants go in `config.py`. Import from there.
- The SQLite DB path is always `config.DB_PATH`. Never construct it inline.

### Imports
- Standard library first, then third-party, then local — separated by blank lines.
- Never use wildcard imports (`from x import *`).

---

## 4. Testing Rules

- **Every function that contains business logic must have a test.**
- Tests use `pytest`. Run with `pytest tests/ -v` from the project root.
- Never mark a task complete without running the tests and confirming they pass.
- Tests must be deterministic. No network calls in unit tests — mock them.
- For scanner and breadth logic: use small, in-memory pandas DataFrames with known values, not live data.

```python
# Good test pattern for scanner logic
def test_momentum_burst_detects_5_percent_move():
    df = pd.DataFrame({
        'close': [100, 100, 100, 100, 105],
        'volume': [1000, 1000, 1000, 1000, 2500],
        'symbol': ['TEST'] * 5,
        'date': pd.date_range('2024-01-01', periods=5)
    })
    result = detect_momentum_burst(df, min_pct=5.0, min_vol_ratio=1.5)
    assert len(result) == 1
    assert result.iloc[0]['symbol'] == 'TEST'
```

---

## 5. Data and Database Rules

- The SQLite schema is defined in `src/ingestion/store.py`. Do not create tables anywhere else.
- Never run raw SQL strings with f-strings. Use parameterized queries: `cursor.execute("SELECT * FROM ohlcv WHERE symbol = ?", (symbol,))`.
- All database operations must handle `sqlite3.OperationalError` gracefully with a logged error.
- The `data/` directory is gitignored. Never commit `.db` files.

---

## 6. NSE Data Specifics

- NSE market hours: 9:15 AM – 3:30 PM IST (Monday–Friday)
- Data pull runs at **16:30 IST** to allow NSE to publish final EOD data
- NSE holidays must be handled — skip pull on exchange holidays, do not treat a missing day as an error
- Symbol format: NSE uses `RELIANCE`, `TCS`, `INFY` — no `.NS` suffix in the DB (unlike Yahoo Finance)
- NIFTY 500 is the primary universe (~500 large/mid cap stocks). NSE Total Market is the extended universe (~2000 stocks). Start with NIFTY 500 for Phase 1.
- Corporate actions (splits, bonuses, dividends) affect historical prices. Flag this in any backtest — do not assume prices are adjusted without verifying the data source.

---

## 7. Commit Discipline

- Commit after every completed task step, not after a large batch of work.
- Commit message format: `type(scope): description`
  - Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`
  - Examples:
    - `feat(ingestion): add NSE EOD fetch for NIFTY 500`
    - `test(monitor): add breadth calculation unit tests`
    - `fix(scanner): correct volume ratio threshold off-by-one`
- Never commit broken code. If tests fail, fix them before committing.

---

## 8. Updating Progress

After completing each task, update `docs/plans/PROGRESS.md`:
- Mark the task as done with date: `✅ 2026-04-11 — Task 1: Data schema and store`
- Note any deviations from the plan and why
- Note any follow-up items discovered during the task

---

## 9. What This Project Is Not

- **Not an automated trading bot.** All execution is manual. The system scans, alerts, and informs. The human decides and places orders.
- **Not a backtesting engine (yet).** Phase 1 is forward-looking. Backtesting comes in Phase 3.
- **Not a real-time system.** EOD data only. No intraday data. No websocket feeds.
- **Not connected to a broker (yet).** Phase 1 uses free NSE data only. Broker API (Zerodha Kite) is a future phase.

---

## 10. When You Are Uncertain

If anything in the plan is unclear, ambiguous, or seems wrong:
1. State your assumption explicitly in a comment: `# ASSUMPTION: treating 0 volume as market holiday`
2. Note it in `docs/plans/PROGRESS.md` under "Open Questions"
3. Continue with the stated assumption rather than blocking

Do not silently make a decision that changes architecture or data models. Those need human review.

---

## 11. Phase 1 MVP — What Success Looks Like

Phase 1 is complete when this script runs successfully every weekday evening:

```bash
python scripts/daily_briefing.py
```

And produces output like:
```
=== Dhanustambha Daily Briefing — 2026-04-11 ===

MARKET MONITOR
  Stocks above MA20:     58% (↑ from 54% yesterday)
  New 52w highs:         47  |  New 52w lows: 12
  Up-volume ratio:       0.68
  Verdict:               OFFENSIVE ✅

TOP MOMENTUM BURST CANDIDATES (5)
  SYMBOL        %CHNG   VOL_RATIO   SECTOR
  DIXON          +8.2      3.4x      Consumer Electronics
  ...

TOP EPISODIC PIVOT CANDIDATES (3)
  SYMBOL        %CHNG   CATALYST    DAYS_SINCE_EVENT
  POLYCAB        +6.1   Earnings    2
  ...

Watchlist saved to: data/watchlists/2026-04-11.csv
```

Everything else is scaffolding to support this output.
