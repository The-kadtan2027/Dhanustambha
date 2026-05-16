# Breadth Dashboard (Sub-Project 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the text-only Market Monitor panel into a visual command-centre with: (1) three radial gauge arcs for the three Offensive/Defensive threshold metrics, (2) a High/Low ratio bar showing market internals, and (3) a full-width historical breadth line chart showing `pct_above_ma20` and `up_volume_ratio` over the stored briefing dates — all without replacing any existing data.

**Architecture:** A new shared `BreadthGauges.tsx` component uses `recharts` `RadialBarChart` / `LineChart`. It receives the current `market` object plus an array of historical `Market` readings fetched from the existing `GET /briefing/dates` + `GET /briefing/{date}` endpoints. A new `GET /market/breadth/history` FastAPI endpoint batches this into a single call. The component is injected below the existing `metricGrid` in `MarketPanel`, which stays untouched.

**Tech Stack:** `recharts` v2 (MIT, no API key), Python/FastAPI, existing SQLite `breadth` table.

---

## File Map

| File | Change |
|---|---|
| `src/api/main.py` | Add `GET /market/breadth/history?days=60` |
| `tests/test_api.py` | Test for the new breadth history endpoint |
| `frontend/app/components/BreadthGauges.tsx` | **NEW** — gauges + line chart |
| `frontend/app/dashboard-client.tsx` | Inject `BreadthGauges` below metric grid in `MarketPanel`; add history fetch |

---

## Task 1: Backend — `GET /market/breadth/history`

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api.py`

### Step 1.1 — Write the failing test

Append to `tests/test_api.py`:

```python
def test_breadth_history_endpoint_returns_rows(api_client):
    """GET /market/breadth/history should return a list of breadth rows."""
    import sqlite3
    conn = sqlite3.connect(__import__("config").DB_PATH)
    conn.execute("""
        INSERT OR IGNORE INTO breadth
          (date, pct_above_ma20, pct_above_ma50, new_highs_52w, new_lows_52w,
           up_volume_ratio, advancing, declining, verdict)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, ("2026-05-01", 60.0, 55.0, 80, 10, 0.65, 300, 200, "OFFENSIVE"))
    conn.commit()
    conn.close()

    response = api_client.get("/market/breadth/history?days=60")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 1
    first = payload["items"][0]
    for key in ("date", "pct_above_ma20", "up_volume_ratio", "verdict"):
        assert key in first, f"Missing key: {key}"
```

### Step 1.2 — Run to confirm FAIL

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_breadth_history_endpoint_returns_rows -v
```
Expected: FAIL with 404 or attribute error.

### Step 1.3 — Implement the endpoint

Add the following import to `src/api/main.py` (alongside existing `store` imports):
```python
from src.ingestion.store import get_breadth_history
```

Add the route after `GET /market/breadth/{date}`:

```python
@app.get("/market/breadth/history")
def breadth_history(days: int = 60) -> Dict[str, Any]:
    """Return the last N days of stored breadth readings, oldest first."""
    rows = get_breadth_history(days=days)
    return {"count": len(rows), "items": rows}
```

Then add `get_breadth_history` to `src/ingestion/store.py` after the existing `get_breadth` function:

```python
def get_breadth_history(days: int = 60) -> list[dict]:
    """Return the most recent `days` breadth rows from the DB, oldest first.

    Returns:
        List of dicts keyed by breadth column names.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT date, pct_above_ma20, pct_above_ma50, new_highs_52w,
                      new_lows_52w, up_volume_ratio, advancing, declining, verdict
               FROM breadth
               ORDER BY date DESC
               LIMIT ?""",
            (days,),
        )
        cols = [d[0] for d in cursor.description]
        rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
        rows.reverse()   # oldest first for charting
        return rows
    except sqlite3.OperationalError as exc:
        logger.error("breadth_history query failed: %s", exc)
        return []
```

### Step 1.4 — Run to confirm PASS

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_breadth_history_endpoint_returns_rows -v
```
Expected: PASS.

### Step 1.5 — Run full API test suite

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py -v
```
Expected: All pass.

### Step 1.6 — Commit

```bash
git add src/api/main.py src/ingestion/store.py tests/test_api.py
git commit -m "feat(api): add get /market/breadth/history endpoint"
```

---

## Task 2: Install Recharts

**Files:**
- `frontend/package.json` (managed by npm)

### Step 2.1 — Install recharts

```powershell
cd d:\antigravity\Dhanustambha\frontend
npm install recharts
```

Expected: `recharts` entry in `package.json` `dependencies`.

### Step 2.2 — Commit

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add recharts dependency"
```

---

## Task 3: Build `BreadthGauges` component

**Files:**
- Create: `frontend/app/components/BreadthGauges.tsx`

### Step 3.1 — Create the component

The component takes:
- `market: Market` — the latest breadth snapshot for the gauge arcs
- `history: Market[]` — array of breadth rows for the line chart (oldest first)

Create `frontend/app/components/BreadthGauges.tsx`:

```tsx
"use client";

import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { Market } from "../dashboard-client";

type Props = {
  market: Market;
  history: Market[];
};

// The three threshold boundaries used by the Market Monitor verdict
const OFFENSIVE_MA20 = 55;
const DEFENSIVE_MA20 = 45;
const OFFENSIVE_UPVOL = 0.60;

function gaugeColor(value: number, offensive: number, defensive: number): string {
  if (value >= offensive) return "#22c55e";
  if (value >= defensive) return "#f59e0b";
  return "#ef4444";
}

function GaugeArc({
  label,
  value,
  max,
  color,
  unit = "",
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  unit?: string;
}) {
  const pct = Math.min(100, (value / max) * 100);
  const data = [{ name: label, value: pct, fill: color }];
  return (
    <div style={{ textAlign: "center", flex: "1 1 0" }}>
      <ResponsiveContainer width="100%" height={100}>
        <RadialBarChart
          innerRadius="65%"
          outerRadius="100%"
          startAngle={210}
          endAngle={-30}
          data={data}
          barSize={8}
        >
          {/* Background track */}
          <RadialBar
            dataKey="value"
            cornerRadius={4}
            background={{ fill: "rgba(0,0,0,0.08)" }}
          />
        </RadialBarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: "-12px" }}>
        <span style={{ fontSize: "18px", fontWeight: 700, color }}>
          {value.toFixed(value < 10 ? 2 : 1)}{unit}
        </span>
        <br />
        <span style={{ fontSize: "11px", color: "var(--muted, #62717f)", textTransform: "uppercase", letterSpacing: "0.5px" }}>
          {label}
        </span>
      </div>
    </div>
  );
}

function HighLowBar({ highs, lows }: { highs: number; lows: number }) {
  const total = highs + lows || 1;
  const highPct = (highs / total) * 100;
  return (
    <div style={{ marginTop: "16px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", color: "var(--muted, #62717f)", marginBottom: "4px" }}>
        <span style={{ textTransform: "uppercase", letterSpacing: "0.5px" }}>52w Highs / Lows</span>
        <span style={{ color: highs > lows ? "#22c55e" : "#ef4444", fontWeight: 700 }}>
          {highs} / {lows}
        </span>
      </div>
      <div style={{ height: "8px", borderRadius: "4px", background: "rgba(0,0,0,0.08)", overflow: "hidden" }}>
        <div
          style={{
            height: "100%",
            width: `${highPct}%`,
            background: highs > lows * 2 ? "#22c55e" : highs > lows ? "#f59e0b" : "#ef4444",
            borderRadius: "4px",
            transition: "width 0.4s ease",
          }}
        />
      </div>
    </div>
  );
}

export default function BreadthGauges({ market, history }: Props) {
  const ma20 = market.pct_above_ma20 ?? 0;
  const ma50 = market.pct_above_ma50 ?? 0;
  const upvol = market.up_volume_ratio ?? 0;
  const highs = market.new_highs_52w ?? 0;
  const lows = market.new_lows_52w ?? 0;

  // Format history for Recharts: keep date short (MM-DD)
  const chartData = history.map((h) => ({
    date: h.date?.slice(5) ?? "",           // "2026-05-08" → "05-08"
    ma20: h.pct_above_ma20 ?? null,
    upvol: h.up_volume_ratio != null ? +(h.up_volume_ratio * 100).toFixed(1) : null,
  }));

  return (
    <div style={{ marginTop: "16px" }}>
      {/* --- Gauge row --- */}
      <div style={{ display: "flex", gap: "8px", alignItems: "flex-end" }}>
        <GaugeArc
          label="Above MA20"
          value={ma20}
          max={100}
          unit="%"
          color={gaugeColor(ma20, OFFENSIVE_MA20, DEFENSIVE_MA20)}
        />
        <GaugeArc
          label="Above MA50"
          value={ma50}
          max={100}
          unit="%"
          color={gaugeColor(ma50, 50, 40)}
        />
        <GaugeArc
          label="Up Volume"
          value={upvol * 100}
          max={100}
          unit="%"
          color={gaugeColor(upvol, OFFENSIVE_UPVOL, 0.5)}
        />
      </div>

      {/* --- Highs/Lows bar --- */}
      <HighLowBar highs={highs} lows={lows} />

      {/* --- Historical breadth line chart --- */}
      {chartData.length >= 2 && (
        <div style={{ marginTop: "20px" }}>
          <div style={{ fontSize: "11px", color: "var(--muted, #62717f)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "6px" }}>
            Breadth History (last {chartData.length} sessions)
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.07)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 10, fill: "var(--muted,#62717f)" }}
                interval="preserveStartEnd"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10, fill: "var(--muted,#62717f)" }}
              />
              <Tooltip
                contentStyle={{ background: "var(--panel,#fff)", border: "1px solid var(--line,#d7dee5)", fontSize: "12px" }}
              />
              <Legend iconType="plainline" wrapperStyle={{ fontSize: "11px" }} />
              {/* Offensive threshold reference */}
              <Line
                type="monotone"
                dataKey="ma20"
                name="% Above MA20"
                stroke="#818cf8"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="upvol"
                name="Up Volume %"
                stroke="#f59e0b"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
```

### Step 3.2 — Commit

```bash
git add frontend/app/components/BreadthGauges.tsx
git commit -m "feat(ui): add BreadthGauges component with radial gauges and line chart"
```

---

## Task 4: Integrate gauges into `MarketPanel`

**Files:**
- Modify: `frontend/app/dashboard-client.tsx`

### Step 4.1 — Add history state and fetch

`MarketPanel` currently receives only `market: Market | null`. We need to add a fetch for history and pass it to the gauge component. The cleanest way is to fetch history inside `MarketPanel` itself using `useEffect`.

Add the import at the top of `dashboard-client.tsx` (alongside existing CandleChart import):
```tsx
import BreadthGauges from "./components/BreadthGauges";
```

Modify `MarketPanel` signature to also accept `apiBaseUrl`:
```tsx
function MarketPanel({ market, apiBaseUrl }: { market: Market | null; apiBaseUrl: string }) {
```

Add state and effect inside `MarketPanel` (after the `if (!market)` guard's closing block, before the return):
```tsx
  const [breadthHistory, setBreadthHistory] = useState<Market[]>([]);

  useEffect(() => {
    if (!market) return;
    fetch(`${apiBaseUrl}/market/breadth/history?days=60`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setBreadthHistory(data.items ?? []))
      .catch(() => setBreadthHistory([]));
  }, [market, apiBaseUrl]);
```

Add `<BreadthGauges>` below the existing `<div className="metricGrid">` in the return JSX (after the closing `</div>` of `metricGrid`):
```tsx
      <BreadthGauges market={market} history={breadthHistory} />
```

### Step 4.2 — Update all call sites

Find where `<MarketPanel>` is rendered in the `DashboardClient` return and add `apiBaseUrl`:
```tsx
<MarketPanel market={briefing?.market ?? null} apiBaseUrl={apiBaseUrl} />
```

### Step 4.3 — Build to verify TypeScript

```powershell
cd d:\antigravity\Dhanustambha\frontend
npm run build
```
Expected: `Exit code: 0`.

### Step 4.4 — Commit

```bash
git add frontend/app/dashboard-client.tsx
git commit -m "feat(ui): embed BreadthGauges in Market Monitor panel"
```

---

## Verification Plan

### Automated Tests

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py -v
```
All previous tests plus `test_breadth_history_endpoint_returns_rows` must pass.

### Next.js Build

```powershell
cd d:\antigravity\Dhanustambha\frontend && npm run build
```
Expected: `Exit code: 0`, no TypeScript errors.

### Manual Visual Verification

```powershell
# Terminal 1 — backend
& "C:\Program Files\Python312\python.exe" -m uvicorn src.api.main:app --reload

# Terminal 2 — frontend
cd d:\antigravity\Dhanustambha\frontend && npm run dev
```

1. Open `http://localhost:3000`. The **Market Monitor** card should now show:
   - **Three radial arc gauges** (green/amber/red) for Above MA20, Above MA50, Up Volume — with numeric value and label below each arc.
   - **One horizontal progress bar** for 52w Highs vs Lows (green if highs > 2×lows, amber if greater, red otherwise).
   - **Line chart** below the bar (visible only when ≥2 historical breadth sessions exist), showing % Above MA20 (indigo) and Up Volume % (amber) over time.
2. Verify the **existing text metrics grid** (6 metric boxes) is still fully visible above the gauges — no content was removed.
3. Resize the browser — all charts should be fluid (ResponsiveContainer).
