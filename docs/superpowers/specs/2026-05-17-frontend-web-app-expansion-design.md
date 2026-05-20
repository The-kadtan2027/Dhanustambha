# Frontend Web App Expansion — Comprehensive Design Spec

**Date:** 2026-05-17  
**Status:** Approved for implementation  
**Implementation plan:** `docs/superpowers/plans/2026-05-17-frontend-web-app-expansion-plan.md` *(to be written)*

---

## Problem Statement

The current UI is a single-page, all-in-one dashboard (`dashboard-client.tsx`, 797 lines) that renders every domain — Market Monitor, Watchlist, Trade Book, and Trade Summary — in a single overcrowded grid. A second partial page exists (`/trades`) but has its own duplicated header, navigation, and utilities. There is no Scanners page, no Journal/Review page, no persistent navigation, and no shared design system. The result is a data terminal, not a trader's personal systematic web app.

---

## Existing State Audit (read before touching anything)

| File | Lines | What it does | Action |
|---|---|---|---|
| `app/page.tsx` | 45 | Server Component: fetches 5 API endpoints, passes props to `DashboardClient` | Refactor to fetch fewer endpoints; homepage becomes Market Monitor + Actions only |
| `app/dashboard-client.tsx` | 797 | All state + all panels in one file. Contains shared types & utilities. | **Decompose** into shared modules; do NOT delete |
| `app/trades/page.tsx` | ~30 | Server Component for `/trades`, passes data to `TradeClient` | Keep as-is; minor updates for shared layout |
| `app/trades/trade-client.tsx` | 259 | Fully built: open positions, modify-stop, close-trade, chart. | Keep most logic; integrate new sidebar layout |
| `app/components/BreadthGauges.tsx` | ~150 | Recharts breadth gauges + line charts | Move to `components/market/` namespace |
| `app/components/CandleChart.tsx` | ~140 | Lightweight candle/MA chart | Move to `components/charts/` namespace |
| `app/globals.css` | ~200 | Full design system CSS variables + utility classes | Keep; extend with sidebar layout tokens |
| `app/layout.tsx` | ~15 | Minimal HTML shell | Extend with sidebar navigation |
| `src/api/main.py` | 394 | FastAPI: breadth, watchlist, briefing, quotes, open/close trades | Extend with `/trades/closed` and `POST /trades/{id}/review` |

---

## Goals

1. **Multi-page routing** — dedicated routes for each domain.
2. **Persistent sidebar navigation** — always-visible, no full-page reload.
3. **Shared code layer** — types, utilities, and UI primitives in one place.
4. **Scanners page** — full data grid with per-scanner filter tabs and candidate detail.
5. **Journal / Review page** — closed trades list + qualitative review form per trade.
6. **No regressions** — existing Trade Book (`/trades`) functionality is preserved entirely.

---

## Page Map (Final Routing Structure)

| Route | Title | Primary Content |
|---|---|---|
| `/` | Dashboard | Market verdict, breadth gauges, required actions, quick stats |
| `/scanners` | Scanners | MB / EP / TI tabs, full watchlist grid, candidate detail + chart, execute |
| `/trades` | Trade Book | Open positions table, modify-stop and close-trade inline forms, charts |
| `/journal` | Review Journal | Closed trades list, journal form (grade, rule-followed, notes), expectancy stats |

---

## Architecture: Shared Code Extraction

The current approach of duplicating `formatCurrency`, `formatNumber`, `fetchJson`, and type definitions across `dashboard-client.tsx` and `trade-client.tsx` must stop. The refactoring creates two shared modules:

### `frontend/types/api.ts` *(NEW)*
All TypeScript types used across pages:
- `Market`, `WatchlistItem`, `Briefing`, `DateList`
- `Trade`, `TradeList`, `TradeSummary`
- `TradeQuote`, `ClosedTrade`, `TradeReview`

### `frontend/lib/format.ts` *(NEW)*
Shared formatting utilities lifted from `dashboard-client.tsx`:
- `formatNumber(value, digits)`, `formatCurrency(value)`, `verdictClass(verdict)`, `setupLabel(setup_type, notes)`

### `frontend/lib/api.ts` *(NEW)*
Centralized fetch helper used by all page-level Server Components:
- `fetchJson<T>(path, options?)` — wraps `fetch`, returns `T | null`, no throwing.

---

## Layout: Sidebar Navigation

### `frontend/app/layout.tsx` *(MODIFY)*
Wrap children in a two-column shell: fixed-width sidebar + scrollable main content area. Add `<Sidebar />` component. Import `Inter` or `Outfit` font from Google Fonts (currently using system font).

### `frontend/app/components/navigation/Sidebar.tsx` *(NEW)*
Persistent vertical navigation. Items:
- **Dhanustambha** logo/wordmark at the top
- Market Monitor pill (shows live verdict colour: green/amber/red) fetched client-side
- Nav links: Dashboard, Scanners, Trade Book, Journal
- Account size input (persisted to `localStorage`) — moved here from the per-page topbar
- API status pill at the bottom

The sidebar replaces the per-page `<header className="topbar">` pattern in both `dashboard-client.tsx` and `trade-client.tsx`. Those headers are removed after the sidebar is in place.

---

## Page 1: Dashboard (`/`)

### `frontend/app/page.tsx` *(MODIFY)*
Slim down: fetch only `/briefing/latest`, `/briefing/dates`, `/trades/actions`, `/trades/summary`. Open trades no longer loaded here — they live on `/trades`.

### `frontend/app/dashboard-client.tsx` *(MODIFY — decompose, do not delete)*
**Keep:** `MarketPanel` (with `BreadthGauges`), `TradeActionsPanel`, `SummaryPanel`, date selector, error/retry logic.

**Remove from this file and relocate:** `WatchlistPanel`, `CandidateDetailPanel`, `OpenTradesPanel` — these move to their dedicated pages.

**Update:** Remove duplicate `formatCurrency` / `formatNumber` / types; import from `lib/format.ts` and `types/api.ts`.

**Result:** `dashboard-client.tsx` becomes ~250 lines focused on market state + action alerts.

---

## Page 2: Scanners (`/scanners`) *(NEW ROUTE)*

### `frontend/app/scanners/page.tsx` *(NEW)*
Server Component. Fetches `/briefing/latest` and `/briefing/dates`. Passes data to `ScannerClient`.

### `frontend/app/scanners/scanner-client.tsx` *(NEW)*
Full-featured client component:
- **Date selector** (reuse pattern from `dashboard-client.tsx`)
- **Scanner filter tabs**: ALL / MOMENTUM BURST / EP / TREND INTENSITY — filters the watchlist grid client-side
- **Watchlist data grid**: Symbol, Setup label (with A+/HIGH badge), % Chg, Vol Ratio, Close, Score columns; sortable by clicking column header; rows are clickable
- **Candidate Detail panel** (moved from `dashboard-client.tsx`): shows metrics, notes, 90-day OHLCV chart, and the Execute trade ticket form with backend quote

---

## Page 3: Trade Book (`/trades`)

### `frontend/app/trades/page.tsx` *(MODIFY — minor)*
No logic change. Add `<Sidebar />` via layout (automatic). Remove the hardcoded `<a href="/">Dashboard</a>` nav link in the header (sidebar handles it).

### `frontend/app/trades/trade-client.tsx` *(MODIFY — minor)*
Remove the per-page `<header className="topbar">` block (replaced by sidebar). Remove the duplicate `formatCurrency` / `formatNumber` helpers; import from `lib/format.ts`. Remove the `<Home />` navigation link. Everything else — open trades table, modify-stop form, close-trade form, chart — **stays unchanged**.

---

## Page 4: Journal (`/journal`) *(NEW ROUTE)*

### `frontend/app/journal/page.tsx` *(NEW)*
Server Component. Fetches `/trades/closed` (new endpoint) and `/trades/summary`. Passes data to `JournalClient`.

### `frontend/app/journal/journal-client.tsx` *(NEW)*
Two-section layout:
1. **Closed Trades List**: table of all closed trades (symbol, setup, entry/exit, P&L, R-multiple, grade, days held, status). Each row is expandable/clickable.
2. **Journal Review Form** (for the selected trade): entry-rule-followed toggle, exit-rule-followed toggle, qualitative notes textarea, grade selector (A/B/C). Calls `POST /trades/{id}/review`. Shows existing review if already submitted.
3. **Expectancy Panel**: reuse `SummaryPanel` component to show rolling closed-trade stats.

---

## Backend Changes (`src/api/main.py`)

### New: `GET /trades/closed` *(NEW ENDPOINT)*
Returns all closed trades (`status != 'OPEN'`) with entry, exit, P&L, days held, R-multiple. Used by the Journal page.

```python
# Response shape
{ "count": int, "items": [ { id, symbol, setup_type, entry_date, exit_date,
                              entry_price, exit_price, shares, pnl, status,
                              grade, notes, days_held, r_multiple } ] }
```

### New: `POST /trades/{id}/review` *(NEW ENDPOINT)*
Saves or updates a qualitative trade review. Creates a row in the new `trade_reviews` table.

```python
# Request body
{ "entry_rule_followed": bool, "exit_rule_followed": bool,
  "what_to_improve": str, "review_date": str }

# Response
{ "status": "saved", "trade_id": int }
```

### New Pydantic models
`TradeReviewRequest` model in `main.py`.

---

## Database Changes

### New table: `trade_reviews` *(in `src/ingestion/store.py`)*

```sql
CREATE TABLE IF NOT EXISTS trade_reviews (
    trade_id                INTEGER PRIMARY KEY,
    entry_rule_followed     INTEGER,   -- 1 = yes, 0 = no
    exit_rule_followed      INTEGER,   -- 1 = yes, 0 = no  
    what_to_improve         TEXT,
    review_date             TEXT,
    FOREIGN KEY (trade_id) REFERENCES trades(id)
);
```

The `init_db()` function in `store.py` must include this `CREATE TABLE IF NOT EXISTS` so it is auto-migrated on first startup.

### Affected functions in `store.py`
- Add `get_closed_trades()` — returns all trades where `status != 'OPEN'` with a calculated `days_held` and `r_multiple`.
- Add `save_trade_review(trade_id, entry_rule_followed, exit_rule_followed, what_to_improve, review_date)` — upsert into `trade_reviews`.
- Add `get_trade_review(trade_id)` — fetch existing review for a trade.

---

## Config Changes (`config.py`)

Only one addition is warranted (backend constant, not a UI toggle):

```python
REVIEW_EXPECTANCY_LOOKBACK_DAYS = 90   # Days of closed trades to include in expectancy stats
```

> **Not added:** `UI_DEFAULT_THEME` — this is a frontend concern and belongs in Next.js config/CSS, not in the Python backend config.

---

## UI Primitive Components (NEW)

To avoid the current copy-paste of `Card`, `Metric`, and `EmptyState` across files:

| File | What it is |
|---|---|
| `frontend/app/components/ui/Card.tsx` | Lifted from `dashboard-client.tsx` |
| `frontend/app/components/ui/Metric.tsx` | Lifted from `dashboard-client.tsx` |
| `frontend/app/components/ui/EmptyState.tsx` | Lifted from `dashboard-client.tsx` |
| `frontend/app/components/ui/Badge.tsx` | NEW — for A+/HIGH/grade labels |

---

## Visual Design Principles

The existing `globals.css` already defines a clean dark design system with CSS variables (`--bg-base`, `--text-main`, `--text-good`, `--text-bad`, `--text-warn`, `--border-subtle`). We will extend it, not replace it:

- **Sidebar**: ~220px fixed left column, dark background (`--bg-card`), with vertical nav items using the existing `--text-brand` colour for active state.
- **Journal form**: uses existing input/button styling from `globals.css`.
- **Scanner tabs**: use the existing `.segmented` button group pattern already in `globals.css` and used in `TradeActionsPanel`.
- **Sortable columns**: add a small `↑↓` indicator to column headers; sort state is client-side `useState`.

---

## ADR Impact

No existing ADRs are contradicted. One new ADR is added:

### ADR-009 — Multi-page routing over single-page monolith

**Date:** 2026-05-17  
**Status:** Accepted  
**Decision:** Split the monolithic dashboard into domain-specific Next.js routes (`/`, `/scanners`, `/trades`, `/journal`), share code via `types/api.ts` and `lib/format.ts`, and unify navigation through a persistent sidebar in `layout.tsx`.  
**Rationale:** The single-file approach produced a 797-line component with tangled state. Route separation matches the 5-layer architecture: each route surfaces one layer's concerns. The Next.js App Router handles routing with zero additional infrastructure.  
**Consequence:** `dashboard-client.tsx` shrinks from 797 lines to ~250 lines; it is not deleted because it is the SSR entry point for `/`.

---

## Test Plan

### 1. Backend API Tests (pytest)
Run: `C:\Program Files\Python312\python.exe -m pytest tests\test_api.py -v`

New tests to add in `tests/test_api.py`:
- `GET /trades/closed` returns an empty list when no closed trades exist.
- `GET /trades/closed` returns correctly shaped objects (r_multiple, days_held fields).
- `POST /trades/{id}/review` saves a review for an existing closed trade.
- `POST /trades/{id}/review` returns 404 for a non-existent trade ID.
- `POST /trades/{id}/review` for an already-reviewed trade overwrites (upsert semantics).

### 2. Frontend Build Test
Run: `cmd /c cd frontend && npm run build`

Verifies: no TypeScript errors, no import mismatches after decomposition, no broken React hook rules across routes.

### 3. Playwright Navigation Test (E2E)
Update `frontend/tests/dashboard.spec.ts` (rename to `navigation.spec.ts`):
- Navigate to `http://localhost:3000` — assert sidebar is present, Dashboard link is active.
- Click "Scanners" in sidebar — assert URL is `/scanners` and scanner grid renders.
- Click "Trade Book" — assert URL is `/trades`, open positions table is visible.
- Click "Journal" — assert URL is `/journal`, closed trades list renders (even if empty).

Run: `cmd /c cd frontend && npx playwright test --reporter=line`

### 4. Manual Smoke Test (run both servers first)
Steps:
1. Start API: `python -m uvicorn src.api.main:app --reload`
2. Start UI: `cd frontend && npm run dev`
3. Open `http://localhost:3000`
4. Confirm: sidebar visible with 4 nav items, market verdict badge visible in sidebar.
5. Go to `/scanners` — select a candidate — confirm trade ticket (account size, stop, quote) works.
6. Go to `/trades` — if an open trade exists: click Modify Stop, change the value, confirm. Then test Close.
7. Go to `/journal` — confirm closed trades list shows. Click one — fill in the review form — submit — confirm it reloads and shows the saved review.
