# Dhanustambha — Indian Market Trading Platform

> *धनुस्तंभ — "the arrow at full draw, before release"*
> A systematic, developer-built trading platform for NSE/BSE markets, following Stockbee/Pradeep Bonde's momentum methodology.

---

## For Coding Agents — Read This First

**You are an AI coding agent working on this project. Before writing a single line of code:**

1. Read `docs/architecture/ARCHITECTURE.md` — understand the full system
2. Read `docs/architecture/DECISIONS.md` — understand *why* things are built this way
3. Read `docs/plans/` — find the current active plan and follow it task-by-task
4. Read `AGENT_RULES.md` — your behavioral contract for this project
5. Check `docs/plans/PROGRESS.md` — see what is done and what is next

**Never skip these files. They exist because this project is built incrementally across many sessions.**

---

## What This Is

A personal, zero-cost trading toolbox that implements the Stockbee momentum methodology for Indian markets (NSE/BSE). Built by a developer, for a developer-trader. Runs entirely on homelab hardware — WSL2 on an HP Pavilion or Termux on a rooted Android device.

### Core methodology (Stockbee / Pradeep Bonde)
- **Momentum Burst**: Stocks that explode 5–25% in 3–5 days due to a catalyst. Buy the burst, ride the follow-through, exit quickly.
- **Episodic Pivots (EP)**: Earnings/news-driven structural breakouts that reset a stock's range. These can run for weeks.
- **Trend Intensity Breakout**: Stocks in persistent, low-volatility uptrends breaking to new highs.
- **Market Monitor**: Breadth-based market health check. Only trade aggressively when the market is in Offensive mode. Go to cash in Defensive mode.

### The five layers
| Layer | Purpose | Status |
|---|---|---|
| 1 — Data ingestion | Pull NSE EOD OHLCV into SQLite | 🔲 Not started |
| 2 — Market monitor | Breadth engine → Offensive/Defensive verdict | 🔲 Not started |
| 3 — Setup scanner | Momentum Burst + EP + Trend Intensity scans | 🔲 Not started |
| 4 — Trade management | Position sizing, open trade log, P&L | 🔲 Not started |
| 5 — Review loop | Trade journal, setup analytics, backtester | 🔲 Not started |

### Build order (recommended)
**Phase 1 (MVP):** Layers 1 + 2 + core of Layer 3 → "Daily Morning Briefing" script
**Phase 2:** Layer 4 → Trade management
**Phase 3:** Layer 5 → Review and learning loop
**Phase 4:** UI (Next.js dashboard) on top of the Python/FastAPI backend

---

## Tech Stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Native trading/data ecosystem; pandas, ta-lib, all NSE libraries |
| Data store | SQLite | Zero cost, zero infra, sufficient for EOD data on 2000 stocks |
| API layer | FastAPI | Lightweight, async, auto-generates OpenAPI docs |
| Frontend | Next.js (optional) | Gaju already has fotohaven experience; browser-based UI |
| Scheduler | cron (WSL) / Termux:Boot | Runs daily at 16:30 IST after NSE market close |
| Data source | nsepy / NSE website scraping | Free, no API key needed to start |
| Testing | pytest | Standard, works on WSL and Termux |
| Dependency mgmt | pip + requirements.txt | Simple, no venv complexity on homelab |

---

## Infrastructure — Zero Cost

```
HP Pavilion Gaming Laptop (AMD Ryzen 5 3550H, 16 GB RAM)
  └── WSL2 (Ubuntu 22.04)
        ├── Python 3.11 environment
        ├── SQLite DB: ~/dhanustambha/data/market.db
        ├── cron job: daily 16:30 IST pull
        └── FastAPI server (optional, for UI)

Rooted Android (backup / mobile use)
  └── Termux + TermuxAlpine
        └── Same Python environment, same codebase via git
```

---

## Repository Layout

```
dhanustambha/
├── README.md                   ← You are here
├── AGENT_RULES.md              ← Coding agent contract (read before coding)
├── requirements.txt            ← Python dependencies
├── config.py                   ← Central config (paths, constants, thresholds)
│
├── data/                       ← SQLite DB lives here (gitignored)
│   └── market.db
│
├── src/
│   ├── ingestion/              ← Layer 1: data pull and storage
│   │   ├── fetcher.py          ← NSE data fetch (nsepy / scraper)
│   │   ├── store.py            ← SQLite write logic
│   │   └── scheduler.py        ← cron entry point
│   │
│   ├── monitor/                ← Layer 2: market breadth engine
│   │   ├── breadth.py          ← % above MA, 52w highs/lows, up-volume
│   │   ├── verdict.py          ← Offensive / Defensive / Avoid logic
│   │   └── history.py          ← Store daily breadth readings
│   │
│   ├── scanner/                ← Layer 3: setup detection
│   │   ├── momentum_burst.py   ← Momentum Burst scan
│   │   ├── episodic_pivot.py   ← Episodic Pivot scan
│   │   ├── trend_intensity.py  ← Trend Intensity scan
│   │   └── watchlist.py        ← Merge + rank + export watchlist
│   │
│   ├── trade/                  ← Layer 4: trade management
│   │   ├── sizer.py            ← Position sizing (fixed fractional risk)
│   │   ├── log.py              ← Open/closed trade log
│   │   └── pnl.py              ← P&L calculations
│   │
│   ├── review/                 ← Layer 5: journal and analytics
│   │   ├── journal.py          ← Tag and annotate trades
│   │   ├── analytics.py        ← Win/loss by setup, expectancy
│   │   └── backtest.py         ← Backtest a scan against historical data
│   │
│   └── api/                    ← FastAPI server (Phase 2+)
│       └── main.py
│
├── tests/
│   ├── test_ingestion.py
│   ├── test_monitor.py
│   ├── test_scanner.py
│   └── test_trade.py
│
├── scripts/
│   └── daily_briefing.py       ← Phase 1 MVP entry point (run this each evening)
│
└── docs/
    ├── architecture/
    │   ├── ARCHITECTURE.md     ← Full system design
    │   └── DECISIONS.md        ← Architecture decision records (ADRs)
    ├── plans/
    │   ├── PROGRESS.md         ← What is done / in progress / next
    │   └── 2026-04-11-phase1-mvp.md  ← Active implementation plan
    └── methodology/
        └── STOCKBEE_ADAPTED.md ← Pradeep's methods translated to NSE context
```
