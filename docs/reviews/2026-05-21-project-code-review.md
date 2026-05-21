# Project Code Review Tracker

**Date:** 2026-05-21
**Scope:** Whole project, executed in phases
**Review status:** Phase 2 in progress

## Phases

- [x] Phase 1 setup: create tracker and define review scope
- [x] Phase 1 review: backend/server-side files
- [x] Phase 1 resolutions: backend findings verified and closed
- [x] Phase 2 review: frontend files
- [x] Phase 2 resolutions: frontend findings verified and closed
- [ ] Final pass: consolidate residual risks, unresolved items, and test gaps

## Scope

### Backend / server-side

- `src/api/`
- `src/ingestion/`
- `src/monitor/`
- `src/scanner/`
- `src/review/`
- `src/trade/`
- Python tests under `tests/`

### Frontend

- `frontend/app/`
- `frontend/components/`
- `frontend/lib/`
- `frontend/hooks/`
- `frontend/tests/`

## Backend Review Progress

### Status

- Started inventory and critical-path read-through
- Reviewed first-pass high-risk modules:
  - `src/api/main.py`
  - `src/ingestion/store.py`
  - `src/ingestion/fetcher.py`
  - `src/trade/log.py`
  - `src/trade/sizer.py`
  - `src/scanner/watchlist.py`

### Findings

#### Open

- None

#### Resolved

1. `P1` `src/api/main.py:608-609`
   `POST /briefing/run` invokes `["python", "scripts/daily_briefing.py"]`, but this repo's own docs say the current PowerShell environment has no `python` on `PATH` and requires `C:\Program Files\Python312\python.exe`. In this environment the manual briefing endpoint will fail even when the script itself is healthy.
   Resolution:
   - [x] Switched the endpoint to `sys.executable`
   - [x] Added API coverage for command construction without relying on `python` being on `PATH`

2. `P1` `src/api/main.py:400-418`, `src/trade/log.py:67-100`
   The manual-share path in `POST /trades/open` bypasses quote validation entirely. A caller can submit `shares` directly with an invalid stop or entry and still persist a trade, because `open_trade()` does not validate `stop_price < entry_price`. This allows impossible risk states into the trade book.
   Resolution:
   - [x] Validated entry/stop invariants in the shared `open_trade()` path
   - [x] Added shared trade regression coverage for `stop_price >= entry_price`
   - [x] Added API coverage that maps manual invalid stops to `422`

3. `P2` `src/ingestion/store.py:329-346`
   `get_breadth_history()` opens a SQLite connection and never closes it on the success path or the error path. This endpoint backs chart/history traffic, so repeated requests can leak connections and eventually surface locking or handle exhaustion problems.
   Resolution:
   - [x] Added a `finally: conn.close()` path
   - [x] Added focused coverage that verifies the connection is closed

4. `P2` `src/scanner/watchlist.py:71-82`, `src/ingestion/store.py:435-459`
   Empty watchlists are not persisted as an overwrite. `export_watchlist()` always writes the CSV, but `save_watchlist()` returns early for `[]`, so a rerun for the same date with zero candidates leaves stale rows in SQLite from the earlier non-empty run. The API can then serve a stale watchlist for that date.
   Resolution:
   - [x] Added `clear_watchlist()` and call it for empty exports
   - [x] Added regression coverage for non-empty watchlist followed by empty overwrite on the same date

### Verification

- `C:\Program Files\Python312\python.exe -m pytest tests\ -v`
- Result: `137 passed`

## Frontend Review Progress

### Status

- Reviewed the scanner execution path and trade-book live refresh path after backend fixes were verified
- Verified the frontend production build after the scanner execution fix

### Findings

#### Open

- None

#### Resolved

1. `P1` `frontend/app/scanners/scanner-client.tsx:232-255`, `frontend/app/scanners/scanner-client.tsx:288-307`
   The scanner execution ticket allowed the user to override server-computed shares and submitted `shares` directly to `POST /trades/open`. That bypassed the backend `account_size` sizing path and could allow oversized trades even though `/trades/quote` had already computed a safe quantity.
   Resolution:
   - [x] Removed the editable share override from the scanner execution ticket
   - [x] Restored `Computed Shares` as a read-only server-derived metric
   - [x] Changed trade-open submission to send `account_size` so the backend computes the final share count
   - [x] Updated the scanner E2E selector to match the stable `Execute` button label

## Test Gaps To Revisit

- Browser E2E was not rerun in this pass because it requires the FastAPI server plus Playwright web server. The production Next.js build was run and passed.

## Resolution Log

- 2026-05-21: Resolved all four backend findings and verified the full Python suite at `137 passed`.
- 2026-05-21: Resolved the scanner execution frontend risk-sizing bypass and verified `cmd /c npm run build`.
