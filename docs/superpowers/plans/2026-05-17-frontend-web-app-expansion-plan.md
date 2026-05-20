# Frontend Web App Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the monolithic dashboard into a multi-page personal systematic trading web app by introducing routed pages for Dashboard, Scanners, Trade Book, and Journal.

**Architecture:** Decompose frontend monolith by extracting shared data types and formatting utilities. Next.js App Router will serve distinct pages mapped directly to our architectural layers via a persistent sidebar layout. Backend FastAPI routes will be extended to support Phase 3 journaling, backed by a new `trade_reviews` SQLite table.

**Tech Stack:** Next.js, React, TypeScript, FastAPI, Python, SQLite, Pytest, Playwright.

---

### Task 1: Database Migration for Trade Reviews

**Files:**
- Modify: `src/ingestion/store.py`
- Test: `tests/test_ingestion.py`

- [ ] **Step 1: Write the failing test for `save_trade_review` and `get_closed_trades`**

```python
# texts/test_ingestion.py (add a new test function)
def test_trade_reviews():
    from src.ingestion.store import init_db, save_trade_review, get_closed_trades, get_connection
    import os
    if os.path.exists('data/market.db'):
        os.remove('data/market.db')
    init_db()
    
    # Needs a trade to review
    from src.trade.log import open_trade, close_trade
    trade_id = open_trade("TEST", "EP", "2026-05-17", 100.0, 95.0, 10, "", "A")
    close_trade(trade_id, "2026-05-18", 110.0)
    
    save_trade_review(trade_id, 1, 1, "Good trade", "2026-05-18")
    trades = get_closed_trades()
    
    assert len(trades) > 0
    assert trades[0]["entry_rule_followed"] == 1
    assert trades[0]["exit_rule_followed"] == 1
    assert trades[0]["what_to_improve"] == "Good trade"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Program Files\Python312\python.exe -m pytest tests\test_ingestion.py -v`
Expected: FAIL due to missing functions or schema.

- [ ] **Step 3: Write minimal implementation in `store.py`**

Modify `init_db()` in `src/ingestion/store.py` to add the new table schema:
```python
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trade_reviews (
        trade_id                INTEGER PRIMARY KEY,
        entry_rule_followed     INTEGER,
        exit_rule_followed      INTEGER,
        what_to_improve         TEXT,
        review_date             TEXT,
        FOREIGN KEY (trade_id) REFERENCES trades(id)
    )
    ''')
```

Add the new helper functions inside `store.py`:
```python
def save_trade_review(trade_id: int, entry_rule_followed: int, exit_rule_followed: int, what_to_improve: str, review_date: str) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO trade_reviews (trade_id, entry_rule_followed, exit_rule_followed, what_to_improve, review_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(trade_id) DO UPDATE SET 
                entry_rule_followed=excluded.entry_rule_followed,
                exit_rule_followed=excluded.exit_rule_followed,
                what_to_improve=excluded.what_to_improve,
                review_date=excluded.review_date
        """, (trade_id, entry_rule_followed, exit_rule_followed, what_to_improve, review_date))
        conn.commit()
    finally:
        conn.close()

def get_closed_trades() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, 
                   r.entry_rule_followed, r.exit_rule_followed, r.what_to_improve, r.review_date
            FROM trades t
            LEFT JOIN trade_reviews r ON t.id = r.trade_id
            WHERE t.status != 'OPEN'
            ORDER BY t.exit_date DESC
        """)
        cols = [description[0] for description in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Program Files\Python312\python.exe -m pytest tests\test_ingestion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/store.py tests/test_ingestion.py
git commit -m "feat(store): add trade_reviews schema and closed trades query"
```

---

### Task 2: Backend API Endpoints for Journaling

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/test_api.py
def test_closed_trades_and_review(client):
    res_closed = client.get("/trades/closed")
    assert res_closed.status_code == 200
    
    review_data = {
        "entry_rule_followed": True,
        "exit_rule_followed": True,
        "what_to_improve": "Solid exit.",
        "review_date": "2026-05-17"
    }
    # Assume trade 9999 doesn't exist
    res_review = client.post("/trades/9999/review", json=review_data)
    assert res_review.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Program Files\Python312\python.exe -m pytest tests\test_api.py -v`
Expected: FAIL (404 on endpoints).

- [ ] **Step 3: Write API implementation**

In `src/api/main.py`, define the new model:
```python
class TradeReviewRequest(BaseModel):
    entry_rule_followed: bool
    exit_rule_followed: bool
    what_to_improve: str
    review_date: str
```

Then add the routes:
```python
@app.get("/trades/closed")
def closed_trades() -> Dict[str, Any]:
    from src.ingestion.store import get_closed_trades
    rows = get_closed_trades()
    return {"count": len(rows), "items": rows}

@app.post("/trades/{trade_id}/review")
def api_save_review(trade_id: int, req: TradeReviewRequest) -> Dict[str, Any]:
    from src.ingestion.store import save_trade_review, get_connection
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE id = ?", (trade_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Trade not found.")
    finally:
        conn.close()
        
    save_trade_review(
        trade_id=trade_id,
        entry_rule_followed=int(req.entry_rule_followed),
        exit_rule_followed=int(req.exit_rule_followed),
        what_to_improve=req.what_to_improve,
        review_date=req.review_date
    )
    return {"status": "saved", "trade_id": trade_id}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Program Files\Python312\python.exe -m pytest tests\test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): add closed trades and review endpoints"
```

---

### Task 3: Extract Frontend Shared Modules

**Files:**
- Create: `frontend/types/api.ts`
- Create: `frontend/lib/format.ts`
- Modify: `frontend/app/dashboard-client.tsx`
- Modify: `frontend/app/trades/trade-client.tsx`

- [ ] **Step 1: Create `types/api.ts`**

Move all the `type` definitions (Market, WatchlistItem, Briefing, DateList, Trade, TradeList, TradeSummary, TradeQuote) from `dashboard-client.tsx` into `frontend/types/api.ts`. Add `export` to them.

- [ ] **Step 2: Create `lib/format.ts`**

Move `formatNumber`, `formatCurrency`, `verdictClass`, and `setupLabel` from `dashboard-client.tsx` to `frontend/lib/format.ts`. Export them.

- [ ] **Step 3: Refactor Dashboard & Trade Clients**

Replace local types and utilities in `dashboard-client.tsx` and `trade-client.tsx` with imports from the new modules. E.g.:
```typescript
import { formatCurrency, formatNumber, verdictClass, setupLabel } from "../../lib/format";
import type { Trade, TradeList, WatchlistItem /* etc */ } from "../../types/api";
```

- [ ] **Step 4: Build test**

Run: `cmd /c cd frontend && npm run build`
Expected: Build passes with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/types/api.ts frontend/lib/format.ts frontend/app/dashboard-client.tsx frontend/app/trades/trade-client.tsx
git commit -m "refactor(ui): extract shared types and formatting utilities"
```

---

### Task 4: Layout and Sidebar Component

**Files:**
- Create: `frontend/app/components/navigation/Sidebar.tsx`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Set up Layout CSS**

In `frontend/app/globals.css`, define layout variables if needed, and set up the grid:
```css
.appLayout {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 220px;
  background: var(--bg-card);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  padding: 1rem;
}
.mainContent {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
}
.sidebarNav {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}
.sidebarNavItem {
  text-decoration: none;
  color: var(--text-main);
  padding: 8px 12px;
  border-radius: 4px;
}
.sidebarNavItem:hover, .sidebarNavItem.active {
  background: var(--bg-base);
  color: var(--text-brand);
}
```

- [ ] **Step 2: Implement Sidebar**

Create `frontend/app/components/navigation/Sidebar.tsx`:
```tsx
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

export default function Sidebar() {
  const pathname = usePathname();
  const [accountSize, setAccountSize] = useState(500000);

  useEffect(() => {
    const saved = localStorage.getItem("dhanustambha_account_size");
    if (saved) setAccountSize(Number(saved));
  }, []);

  const handleAccountSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setAccountSize(val);
    localStorage.setItem("dhanustambha_account_size", val.toString());
  };

  return (
    <aside className="sidebar">
      <h2>Dhanustambha</h2>
      <div className="sidebarNav">
        <Link href="/" className={`sidebarNavItem ${pathname === "/" ? "active" : ""}`}>Dashboard</Link>
        <Link href="/scanners" className={`sidebarNavItem ${pathname === "/scanners" ? "active" : ""}`}>Scanners</Link>
        <Link href="/trades" className={`sidebarNavItem ${pathname === "/trades" ? "active" : ""}`}>Trade Book</Link>
        <Link href="/journal" className={`sidebarNavItem ${pathname === "/journal" ? "active" : ""}`}>Journal</Link>
      </div>
      <div style={{ marginTop: "auto", display: "flex", flexDirection: "column", gap: "8px" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: "4px", fontSize: "12px" }}>
          <span>Account Size (₹)</span>
          <input type="number" value={accountSize} onChange={handleAccountSizeChange} step="10000" style={{ padding: "4px", background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", borderRadius: "4px" }} />
        </label>
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Modify Layout**

Update `frontend/app/layout.tsx`:
```tsx
import Sidebar from "./components/navigation/Sidebar";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="appLayout">
          <Sidebar />
          <div className="mainContent">{children}</div>
        </div>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Build test**

Run: `cmd /c cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/components/navigation/Sidebar.tsx frontend/app/layout.tsx frontend/app/globals.css
git commit -m "feat(ui): add persistent sidebar layout and configuration"
```

---

### Task 5: Modularize Dashboard & Page Logic

**Files:**
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/dashboard-client.tsx`
- Modify: `frontend/app/trades/trade-client.tsx`
- Create: `frontend/app/components/ui/Card.tsx`
- Create: `frontend/app/components/ui/Metric.tsx`
- Create: `frontend/app/components/ui/EmptyState.tsx`

- [ ] **Step 1: Extract Shared UI Primitives**

Move `Card`, `Metric`, and `EmptyState` out of `dashboard-client.tsx` into their new files inside `frontend/app/components/ui/` with proper properties and export them.

- [ ] **Step 2: Clean up Topbars**

Remove the `header className="topbar"` component block from both `dashboard-client.tsx` and `trades/trade-client.tsx`, since the sidebar now handles high-level navigation and Account Size setting. Ensure any local accountSize states are replaced; components that need `accountSize` should pull from local storage during `useEffect` (like `ScannerClient` will later).

- [ ] **Step 3: Shrink Dashboard Client**

In `frontend/app/dashboard-client.tsx`, **remove** `WatchlistPanel`, `CandidateDetailPanel`, and `OpenTradesPanel`. Let it export only `MarketPanel`, `TradeActionsPanel`, and `SummaryPanel`. 
Update `frontend/app/page.tsx` to stop parallel fetching `/trades/open`.

- [ ] **Step 4: Build test**

Run: `cmd /c cd frontend && npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app/page.tsx frontend/app/dashboard-client.tsx frontend/app/trades/trade-client.tsx frontend/app/components/ui/
git commit -m "refactor(ui): extract UI primitives and streamline dashboard layout"
```

---

### Task 6: Implement Scanners Module

**Files:**
- Create: `frontend/app/scanners/page.tsx`
- Create: `frontend/app/scanners/scanner-client.tsx`

- [ ] **Step 1: Create Scanners React Component**

Implement `frontend/app/scanners/scanner-client.tsx` by pasting `WatchlistPanel`, `CandidateDetailPanel` (modified to pull `accountSize` from local storage), and utilizing a new top-level component that supports filtering by `ALL | MOMENTUM_BURST | EP | TREND_INTENSITY`.

```tsx
"use client";
import { useState, useEffect } from "react";
import { Briefing, DateList, WatchlistItem } from "../../types/api";
import { Card, EmptyState, Metric } from "../components/ui/Primitives"; // Update custom import
// ... Include CandidateDetailPanel and WatchlistPanel here (ensure proper module imports exist) ...
```
*(Code is abbreviated for brevity; you should implement full behavior mirroring previous dashboard-client functionality)*

- [ ] **Step 2: Create Server-side Route Page**

Implement `frontend/app/scanners/page.tsx`:
```tsx
import ScannerClient from "./scanner-client";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
// Fetch /briefing/latest and /briefing/dates and render <ScannerClient />
```

- [ ] **Step 3: Build test**

Run: `cmd /c cd frontend && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/app/scanners/
git commit -m "feat(ui): add dedicated Scanners route with tabbed view"
```

---

### Task 7: Implement Journal Route

**Files:**
- Create: `frontend/app/journal/page.tsx`
- Create: `frontend/app/journal/journal-client.tsx`

- [ ] **Step 1: Write Journal Client Implementation**

In `frontend/app/journal/journal-client.tsx`, fetch `/trades/closed` and `/trades/summary`.
Render a table for closed trades, and an expandable row or side-panel that POSTs a new review to `/trades/{id}/review` when the user fills out the form.

- [ ] **Step 2: Write Journal Server Component**

In `frontend/app/journal/page.tsx`:
```tsx
// Typical NextJS page passing initial fetch states to JournalClient
```

- [ ] **Step 3: Build test**

Run: `cmd /c cd frontend && npm run build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/app/journal/
git commit -m "feat(ui): add Journal route for closed trade reviews"
```

---

### Task 8: Update Playwright Navigation Tests

**Files:**
- Modify/Rename: `frontend/tests/dashboard.spec.ts` -> `frontend/tests/navigation.spec.ts`

- [ ] **Step 1: Write Playwright E2E Path Flow**

```typescript
// frontend/tests/navigation.spec.ts
import { test, expect } from '@playwright/test';

test('app navigation works smoothly with the new sidebar', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('aside.sidebar')).toBeVisible();

  await page.click('text=Scanners');
  await expect(page).toHaveURL(/\/scanners/);

  await page.click('text=Trade Book');
  await expect(page).toHaveURL(/\/trades/);
  
  await page.click('text=Journal');
  await expect(page).toHaveURL(/\/journal/);
});
```

- [ ] **Step 2: Run End-to-End Test**

Run: `cmd /c cd frontend && npx playwright test --reporter=line`
Expected: All suites passing.

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/
git commit -m "test(e2e): update test suite to navigate fully-fledged application"
```
