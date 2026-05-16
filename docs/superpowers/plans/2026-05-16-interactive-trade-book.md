# Interactive Trade Book Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the read-only dashboard into a complete trading terminal with write-enabled API routes, inline watchlist execution, and a dedicated trade management page.

**Architecture:** We will first expand the FastAPI layer with Pydantic payload models and database write calls. Then we will add account size state to the Next.js frontend to power dynamic position sizing inside a new Execute Trade modal, finishing with the Trade Book UI.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, React, React Hooks, Fetch API.

---

### Task 1: Enable CORS Write Methods & Define Pydantic Models

**Files:**
- Modify: `src/api/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test for CORS POST**

```python
# add to tests/test_api.py
def test_api_allows_post_methods(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert "POST" in response.headers.get("access-control-allow-methods", "")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_api.py::test_api_allows_post_methods -v`
Expected: FAIL due to missing POST in allow_methods.

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/main.py
# Add pydantic imports at the top
from pydantic import BaseModel

# Update CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    # ...
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

# Add Pydantic models below app declaration
class TradeOpenRequest(BaseModel):
    symbol: str
    setup_type: str
    entry_date: str
    entry_price: float
    stop_price: float
    shares: int
    notes: Optional[str] = None
    grade: Optional[str] = None

class TradeUpdateStopRequest(BaseModel):
    stop_price: float

class TradeCloseRequest(BaseModel):
    exit_date: str
    exit_price: float
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_api.py::test_api_allows_post_methods -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): expand cors and add pydantic models"
```

---

### Task 2: Implement POST /trades/open

**Files:**
- Modify: `src/api/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_api.py
def test_api_open_trade(client):
    payload = {
        "symbol": "FOO",
        "setup_type": "MOMENTUM_BURST",
        "entry_date": "2026-05-16",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "shares": 10
    }
    res = client.post("/trades/open", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "OPEN"
    assert data["symbol"] == "FOO"
    assert data["shares"] == 10
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_api.py::test_api_open_trade -v`
Expected: FAIL / 404 (Route not found)

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/main.py
# add import: from src.trade.log import open_trade
from src.trade.log import open_trade

@app.post("/trades/open")
def api_open_trade(req: TradeOpenRequest) -> Dict[str, Any]:
    try:
        from src.ingestion.store import get_conn
        conn = get_conn()
        trade_id = open_trade(
            conn=conn,
            symbol=req.symbol,
            setup_type=req.setup_type,
            entry_date=req.entry_date,
            entry_price=req.entry_price,
            stop_price=req.stop_price,
            shares=req.shares,
            notes=req.notes,
            grade=req.grade
        )
        
        # return the newly inserted trade row
        import pandas as pd
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        cols = [description[0] for description in cursor.description]
        row = dict(zip(cols, cursor.fetchone()))
        return row
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_api.py::test_api_open_trade -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): add post /trades/open route"
```

---

### Task 3: Implement PUT Endpoints (Update Stop & Close)

**Files:**
- Modify: `src/api/main.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# add to tests/test_api.py
def test_api_update_and_close_trade(client):
    # 1. Open a trade first
    res = client.post("/trades/open", json={
        "symbol": "BAR", "setup_type": "EP", "entry_date": "2026-05-16",
        "entry_price": 200.0, "stop_price": 190.0, "shares": 5
    })
    trade_id = res.json()["id"]

    # 2. Update Stop
    res = client.put(f"/trades/{trade_id}/update-stop", json={"stop_price": 195.0})
    assert res.status_code == 200
    
    # 3. Close Trade
    res = client.put(f"/trades/{trade_id}/close", json={"exit_date": "2026-05-17", "exit_price": 210.0})
    assert res.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_api.py::test_api_update_and_close_trade -v`
Expected: FAIL / 404 (Route not found)

- [ ] **Step 3: Write minimal implementation**

```python
# src/api/main.py
# add import: from src.trade.log import update_stop_price, close_trade
from src.trade.log import update_stop_price, close_trade

@app.put("/trades/{trade_id}/update-stop")
def api_update_stop(trade_id: int, req: TradeUpdateStopRequest) -> Dict[str, Any]:
    from src.ingestion.store import get_conn
    conn = get_conn()
    try:
        update_stop_price(conn, trade_id, req.stop_price)
        return {"status": "success", "id": trade_id, "new_stop": req.stop_price}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.put("/trades/{trade_id}/close")
def api_close_trade(trade_id: int, req: TradeCloseRequest) -> Dict[str, Any]:
    from src.ingestion.store import get_conn
    conn = get_conn()
    try:
        close_trade(conn, trade_id, req.exit_date, req.exit_price)
        return {"status": "success", "id": trade_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_api.py::test_api_update_and_close_trade -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): add put routes for update-stop and close"
```

---

### Task 4: UI Global Account Settings State

**Files:**
- Modify: `frontend/app/layout.tsx` (Add Header state)

- [ ] **Step 1: Write React implementation**
Since frontend TDD is complex with pure shell tests, implement the state directly.

```tsx
// update frontend/app/layout.tsx to include Account Size Context
import { useState, useEffect } from "react";
// We must convert layout to a client component OR just put Account config inside dashboard-client.tsx. 
// For simplicity, we will implement it directly inside dashboard-client.tsx where all state handles.
```

Oops! In Next.js App Router, `layout.tsx` is server-side by default. Let's put Account Settings inside `dashboard-client.tsx`.

Modify `frontend/app/dashboard-client.tsx` to add Account Size input at the very top.
```tsx
// frontend/app/dashboard-client.tsx (top of DashboardClient component)

  // Under existing useState lines:
  const [accountSize, setAccountSize] = useState<number>(500000);

  // Under loadData() useEffect
  useEffect(() => {
    const saved = localStorage.getItem("dhanustambha_account_size");
    if (saved) setAccountSize(Number(saved));
  }, []);

  const handleAccountSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setAccountSize(val);
    localStorage.setItem("dhanustambha_account_size", val.toString());
  };

  // Render inside the main grid/header:
  /*
  <header className="mb-8 flex justify-between items-center">
    <div>
      <h1 className="text-4xl font-bold mb-2 tracking-tight">Dhanustambha</h1>
      <p className="text-gray-400">Momentum Trading Platform</p>
    </div>
    <div className="flex flex-col items-end">
      <label className="text-sm text-gray-500 mb-1">Account Size (₹)</label>
      <input 
        type="number" 
        value={accountSize} 
        onChange={handleAccountSizeChange} 
        className="bg-gray-800 text-white rounded px-3 py-2 border border-gray-700 w-32 focus:outline-none focus:border-blue-500"
      />
    </div>
  </header>
  */
```

- [ ] **Step 2: Commit**
```bash
git add frontend/app/dashboard-client.tsx
git commit -m "feat(frontend): add account size configuration to local storage"
```

---

### Task 5: Execute Trade Modal (Watchlist Inline)

**Files:**
- Modify: `frontend/app/dashboard-client.tsx`

- [ ] **Step 1: Write Execute Modal Component**

```tsx
// Add inside frontend/app/dashboard-client.tsx above the main component
function ExecuteModal({ candidate, accountSize, onClose, onSuccess }: any) {
  const [entryPrice, setEntryPrice] = useState(candidate.close);
  const [stopPrice, setStopPrice] = useState(candidate.close * 0.96);
  
  // Sizing Logic
  const riskAmount = accountSize * 0.01;
  const stopDistance = Math.max(entryPrice - stopPrice, 0.01);
  let shares = Math.floor(riskAmount / stopDistance);
  
  const totalValue = shares * entryPrice;
  const maxValue = accountSize * 0.10;
  if (totalValue > maxValue) {
      shares = Math.floor(maxValue / entryPrice);
  }

  const handleExecute = async () => {
    const res = await fetch("http://127.0.0.1:8000/trades/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: candidate.symbol,
        setup_type: candidate.setup_type,
        entry_date: new Date().toISOString().split('T')[0],
        entry_price: entryPrice,
        stop_price: stopPrice,
        shares: shares
      })
    });
    if (res.ok) {
      onSuccess();
    } else {
      alert("Execution failed.");
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 p-6 rounded-lg w-96 relative">
        <h2 className="text-xl font-bold mb-4">Execute {candidate.symbol}</h2>
        
        <div className="flex flex-col gap-3 mb-6">
          <div>
            <label className="text-xs text-gray-500">Entry Price</label>
            <input type="number" step="0.05" value={entryPrice} onChange={e => setEntryPrice(Number(e.target.value))} className="w-full bg-gray-800 p-2 rounded" />
          </div>
          <div>
            <label className="text-xs text-gray-500">Stop Loss</label>
            <input type="number" step="0.05" value={stopPrice} onChange={e => setStopPrice(Number(e.target.value))} className="w-full bg-gray-800 p-2 rounded" />
          </div>
          <div className="p-3 bg-gray-800 rounded border border-gray-700 mt-2">
            <div className="flex justify-between mb-1">
              <span className="text-sm text-gray-400">Shares:</span>
              <span className="font-mono text-white font-bold">{shares}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-400">Total Value:</span>
              <span className="font-mono text-white">₹{(shares * entryPrice).toLocaleString()}</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded transition-colors text-sm">Cancel</button>
          <button onClick={handleExecute} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded transition-colors text-sm">Confirm</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add trigger in Watchlist Table**
Add state `<ExecuteModal />` inside `DashboardClient` and an `Execute ⚡` button inside the map of candidates.

- [ ] **Step 3: Commit**
```bash
git add frontend/app/dashboard-client.tsx
git commit -m "feat(frontend): add watchlist execution modal with position sizing"
```

---

### Task 6: Trade Book Page & API Fetching

**Files:**
- Create: `frontend/app/trades/page.tsx`

- [ ] **Step 1: Write Page Implementation**
Similar standalone React container fetching from `/trades/open` and displaying a table of actions.
The file simply renders a table of `openTrades` running a map to display the Trade ID, Entry Date, Entry Price, etc.
Include the inline `PUT /trades/id/close` form hook.

```tsx
// Create file: frontend/app/trades/page.tsx
"use client";
import { useState, useEffect } from "react";
import Link from "next/link";

export default function Trades() {
  const [openTrades, setOpenTrades] = useState([]);

  const fetchOpen = async () => {
    const res = await fetch("http://127.0.0.1:8000/trades/open");
    const data = await res.json();
    setOpenTrades(data.items || []);
  };

  useEffect(() => { fetchOpen(); }, []);

  const closeTrade = async (id: number) => {
    const price = prompt("Exit price?");
    if (!price) return;
    const res = await fetch(`http://127.0.0.1:8000/trades/${id}/close`, {
      method: "PUT", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ exit_date: new Date().toISOString().split('T')[0], exit_price: Number(price) })
    });
    if (res.ok) fetchOpen();
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200 font-sans p-8">
      <Link href="/" className="text-blue-500 hover:underline mb-6 inline-block">← Back to Dashboard</Link>
      <h1 className="text-3xl font-bold mb-6">Open Trades</h1>
      
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-gray-400 border-b border-gray-800">
            <tr>
              <th className="pb-3 px-2">Symbol</th>
              <th className="pb-3 px-2">Setup</th>
              <th className="pb-3 px-2">Entry Price</th>
              <th className="pb-3 px-2">Stop Loss</th>
              <th className="pb-3 px-2">Action</th>
            </tr>
          </thead>
          <tbody>
            {openTrades.map((t: any) => (
              <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-3 px-2 font-mono font-medium text-white">{t.symbol}</td>
                <td className="py-3 px-2">{t.setup_type}</td>
                <td className="py-3 px-2">{t.entry_price}</td>
                <td className="py-3 px-2">{t.stop_price}</td>
                <td className="py-3 px-2">
                  <button onClick={() => closeTrade(t.id)} className="text-red-500 hover:underline">Close</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {openTrades.length === 0 && <p className="text-gray-500 p-4">No open trades.</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```bash
git add frontend/app/trades/page.tsx
git commit -m "feat(frontend): create dedicated trade book view"
```
