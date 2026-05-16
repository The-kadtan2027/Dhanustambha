# Interactive Trade Book — Design Spec

**Date:** 2026-05-16  
**Phase:** 6 — Paper Trading  
**Status:** Approved by user

---

## Overview

The Dhanustambha dashboard is currently read-only. All trade management happens through the CLI `trade_manager.py`. This spec describes converting the dashboard into a full-featured Paper Trading Terminal, upgrading the FastAPI backend to accept write operations, and adding inline watchlist execution and a dedicated trade book section to the Next.js frontend.

The implementation spans three layers:
1. **FastAPI** — three new write endpoints
2. **Account Settings** — account size stored in browser localStorage, drives auto-sizing
3. **Next.js** — Watchlist Execute modal + Trade Book management page

---

## Part 1: FastAPI Write Endpoints

### Design Decisions
- API currently only allows `GET` methods (enforced in `allow_methods=["GET"]` in CORS). This will be expanded to also allow `POST` and `PUT`.
- All models use Pydantic `BaseModel` for request validation.
- Responses mirror the same `{count, items}` shape as existing read endpoints.

### New Endpoints

#### `POST /trades/open`
Opens a new paper trade.

**Request body:**
```json
{
  "symbol": "POLYCAB",
  "setup_type": "EPISODIC_PIVOT",
  "entry_date": "2026-05-16",
  "entry_price": 5800.0,
  "stop_price": 5568.0,
  "shares": 17,
  "notes": "EP A+ tier — 8% gap on 4.2x volume",
  "grade": "A"
}
```

**Response:** The full newly-created open trade row including `id`, `status = OPEN`, `unrealized_pnl = 0`.

**Backend call:** `open_trade()` in `src/trade/log.py`.

---

#### `PUT /trades/{trade_id}/update-stop`
Moves the stop loss on an open trade (called when the dashboard action flag says TRAIL_TO_BREAKEVEN, TRAIL_TO_3PCT, or TRAIL_TO_7_5PCT).

**Request body:**
```json
{ "stop_price": 5800.0 }
```

**Response:** The updated trade row with `old_stop_price`, `new_stop_price`.

**Backend call:** `update_stop_price()` in `src/trade/log.py`.

---

#### `PUT /trades/{trade_id}/close`
Closes an open trade and records the result.

**Request body:**
```json
{
  "exit_date": "2026-05-20",
  "exit_price": 6200.0
}
```

**Response:** The closed trade row with `status`, `pnl`, `r_multiple`.

**Backend call:** `close_trade()` in `src/trade/log.py`.

---

## Part 2: Account Settings (Frontend)

### Account Size Config
- A small **"Account ₹"** numeric input rendered in the top navigation bar of the dashboard.
- Persisted in `localStorage` under key `dhanustambha_account_size`.
- Defaults to `500000` (₹5,00,000) on first load.
- Used by the trade modal to call the position sizer.

### Position Sizing Logic (frontend-side)
When opening the Execute Trade modal:
```
risk_amount = account_size * 0.01         # 1% risk
stop_distance = entry_price - stop_price
shares_to_buy = floor(risk_amount / stop_distance)
total_value = shares_to_buy * entry_price
max_value = account_size * 0.10           # 10% max position cap
if total_value > max_value:
    shares_to_buy = floor(max_value / entry_price)
```
These fields animate in real-time as the user types their stop loss.

---

## Part 3: Execute Trade Modal (Watchlist Integration)

Each watchlist card/row gains a small **⚡ Execute** button on the right edge.

### Modal Contents
| Field | Behaviour |
|---|---|
| Symbol | Auto-filled from watchlist. Read-only. |
| Setup Type | Auto-filled (e.g. EPISODIC_PIVOT). Read-only. |
| Entry Price | User types. Pre-filled with last close from the row. |
| Stop Price | User types. Suggested default: `close * (1 - setup_stop_pct)`. |
| Shares | Auto-computed, read-only, animates as stop price changes. |
| ₹ Risk | Auto-computed. Shows as `₹X,XXX (1.0%)`. |
| Grade | A / B / C dropdown. Pre-selected based on tier label (A+ → A). |
| Notes | Optional free-text. |

- Clicking **Confirm** posts to `POST /trades/open`.
- On success: modal closes, the Trade Book tab flashes to show the new trade, a short "✅ Trade Logged" toast appears.
- On error: inline error message shown in the modal.

---

## Part 4: Trade Book Page (Frontend)

A dedicated `/trades` page in the Next.js app (new route: `app/trades/page.tsx`).

### Open Positions Table
Columns: `Symbol`, `Setup`, `Entry Date`, `Entry ₹`, `Stop ₹`, `Current ₹`, `P&L`, `Days Held`, `Action`.

- Rows with a non-`NONE` `action_required` flag are highlighted in amber.
- **Action column** inline controls:
  - `🔄 Update Stop`: opens an inline input pre-filled with the suggested new stop level.
  - `✅ Close Trade`: opens a small inline form asking for exit price and date.

### Closed Trades Table
Below the open positions, a collapsible section shows the closed trade history with Win/Loss colouring and the R-multiple column.

### Performance Summary Card
At the very top: a stats bar showing `Win Rate`, `Expectancy (R)`, and `Total Closed Trades` pulled from `GET /trades/summary`.

---

## Data Flow

```
User clicks ⚡ Execute on a Watchlist card
        │
        ▼
Modal opens, auto-fills Symbol + Setup Type
User types Entry Price + Stop Price
        │
        ▼
Frontend computes Shares using Account Size from localStorage
        │
        ▼
User clicks Confirm
        │
        ▼
POST /trades/open  →  open_trade() in src/trade/log.py
        │
        ▼
Trade appears in GET /trades/open  →  Trade Book page
        │
        ▼
Next day: action_required = TRAIL_TO_BREAKEVEN
        │
        ▼
User clicks 🔄 Update Stop  →  types new stop  →  PUT /trades/{id}/update-stop
        │
        ▼
Profit target hit → User clicks ✅ Close Trade  →  PUT /trades/{id}/close
```

---

## Error Handling

- **Backend validation errors** (e.g., stop above entry) → API returns `422 Unprocessable Entity` with a human-readable detail. Frontend shows inline.
- **Trade not found** → `404`. Frontend shows toast: "Trade not found — please reload."
- **DB errors** — logged server-side. Frontend receives a generic `500` and shows: "Something went wrong. Please try again."

---

## Testing Plan

### Backend (pytest)
- `test_api_open_trade_creates_record`: POST → returns 200, trade appears in GET /trades/open.
- `test_api_update_stop_updates_db`: PUT update-stop → old_stop_price vs new_stop_price correct.
- `test_api_close_trade_updates_status`: PUT close → status becomes CLOSED_WIN or CLOSED_LOSS.
- `test_api_invalid_stop_above_entry_rejected`: POST with stop > entry → 422.

### Frontend (Playwright smoke test)
- Modal opens on ⚡ button click.
- Auto-compute fields update when stop price is typed.
- Confirm button posts and modal closes.
- New trade appears in Trade Book page.

---

## Out of Scope (for this spec)

- Real broker integration (ADR-005)
- Intraday data or live price streaming
- Chart embeds (Sub-Project 2)
- Breadth gauges (Sub-Project 3)
