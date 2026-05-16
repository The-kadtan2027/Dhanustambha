# Embedded Charts (TradingView Lightweight Charts) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Embed an interactive candlestick chart (TradingView Lightweight Charts) below the existing metrics in the Candidate Detail panel on the main dashboard, and below the action form in the Trade Book page — showing 90 days of OHLCV with MA20, MA50, entry price, and stop-loss overlays.

**Architecture:** A new FastAPI endpoint `GET /ohlcv/{symbol}?days=90` serves raw candle + MA data from SQLite. A shared `CandleChart` React component fetches and renders that data using `lightweight-charts`. The component is injected _below_ existing content in `CandidateDetailPanel` (dashboard) and in a new collapsible section per row in the Trade Book page.

**Tech Stack:** Python/FastAPI, SQLite, Next.js `"use client"` React, `lightweight-charts` v4 (TradingView, MIT-licensed, ~45KB gzipped, no API key), `pandas` for MA calculation.

---

## File Map

| File | Change |
|---|---|
| `src/api/main.py` | Add `GET /ohlcv/{symbol}` endpoint |
| `tests/test_api.py` | Add test for the new OHLCV route |
| `frontend/app/components/CandleChart.tsx` | **NEW** — shared chart component |
| `frontend/app/dashboard-client.tsx` | Inject `CandleChart` at bottom of `CandidateDetailPanel` |
| `frontend/app/trades/trade-client.tsx` | Inject `CandleChart` per selected position row |

---

## Task 1: Backend — `GET /ohlcv/{symbol}`

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api.py`

### Step 1.1 — Write the failing test

Append this test to `tests/test_api.py`:

```python
def test_ohlcv_endpoint_returns_candles_and_ma(api_client):
    """OHLCV endpoint should return candle rows with MA20 and MA50 columns."""
    from src.ingestion.store import upsert_ohlcv, get_connection
    import sqlite3

    # insert a symbol row so FK constraint of ohlcv is satisfied
    conn = sqlite3.connect(__import__("config").DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO symbols (symbol, name, active) VALUES (?, ?, ?)",
        ("DEMO", "Demo Stock", 1),
    )
    conn.commit()
    conn.close()

    rows = [
        {
            "symbol": "DEMO",
            "date": f"2026-0{1 if i < 9 else 2}-{(i % 28) + 1:02d}",
            "open": 100.0 + i,
            "high": 105.0 + i,
            "low": 98.0 + i,
            "close": 102.0 + i,
            "volume": 500_000,
        }
        for i in range(30)
    ]
    upsert_ohlcv(rows)

    response = api_client.get("/ohlcv/DEMO?days=90")
    assert response.status_code == 200
    payload = response.json()
    assert "candles" in payload
    assert "symbol" in payload
    assert payload["symbol"] == "DEMO"
    assert len(payload["candles"]) >= 1
    first = payload["candles"][0]
    assert "time" in first
    assert "open" in first
    assert "high" in first
    assert "low" in first
    assert "close" in first
    assert "volume" in first
    assert "ma20" in first        # may be null for early rows
    assert "ma50" in first        # may be null for early rows
```

### Step 1.2 — Run to confirm FAIL

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_ohlcv_endpoint_returns_candles_and_ma -v
```
Expected: FAIL with `404` or similar.

### Step 1.3 — Implement the endpoint

Add this import at the top of `src/api/main.py` (after existing ingestion imports):

```python
from src.ingestion.store import get_ohlcv
```

Add the route before the `@app.get("/trades/open")` block:

```python
@app.get("/ohlcv/{symbol}")
def ohlcv_chart(symbol: str, days: int = 90) -> Dict[str, Any]:
    """Return OHLCV candles with rolling MA20/MA50 for the chart component."""
    df = get_ohlcv(symbol.upper(), days=days)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")

    df = df.sort_values("date").reset_index(drop=True)
    df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
    df["ma50"] = df["close"].rolling(50, min_periods=1).mean()

    candles = []
    for _, row in df.iterrows():
        date_str = str(row["date"])
        if hasattr(row["date"], "strftime"):
            date_str = row["date"].strftime("%Y-%m-%d")
        candles.append({
            "time": date_str,
            "open": _clean_value(row["open"]),
            "high": _clean_value(row["high"]),
            "low": _clean_value(row["low"]),
            "close": _clean_value(row["close"]),
            "volume": _clean_value(row["volume"]),
            "ma20": _clean_value(row["ma20"]),
            "ma50": _clean_value(row["ma50"]),
        })

    return {"symbol": symbol.upper(), "days": days, "candles": candles}
```

### Step 1.4 — Run to confirm PASS

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_ohlcv_endpoint_returns_candles_and_ma -v
```
Expected: PASS.

### Step 1.5 — Run full API test suite

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py -v
```
Expected: All pass.

### Step 1.6 — Commit

```bash
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): add get /ohlcv/{symbol} with ma20 ma50"
```

---

## Task 2: Install the frontend chart library

**Files:**
- `frontend/package.json` (managed by npm)

### Step 2.1 — Install lightweight-charts

```powershell
cd d:\antigravity\Dhanustambha\frontend
npm install lightweight-charts
```

Expected: `lightweight-charts` entry appears in `package.json` `dependencies`.

### Step 2.2 — Commit

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(frontend): add lightweight-charts dependency"
```

---

## Task 3: Build the shared `CandleChart` component

**Files:**
- Create: `frontend/app/components/CandleChart.tsx`

### Step 3.1 — Create the component

Create `frontend/app/components/CandleChart.tsx`:

```tsx
"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type HistogramData,
  ColorType,
} from "lightweight-charts";

export type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ma20: number | null;
  ma50: number | null;
};

type Props = {
  candles: Candle[];
  entryPrice?: number | null;
  stopPrice?: number | null;
  height?: number;
};

export default function CandleChart({
  candles,
  entryPrice,
  stopPrice,
  height = 280,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!containerRef.current || candles.length === 0) return;

    // Destroy previous instance when symbol changes
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.05)" },
        horzLines: { color: "rgba(255,255,255,0.05)" },
      },
      crosshair: { mode: 1 },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      timeScale: {
        borderColor: "rgba(255,255,255,0.1)",
        timeVisible: true,
      },
    });
    chartRef.current = chart;

    // --- Candlestick series ---
    const candleSeries = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    const candleData: CandlestickData[] = candles.map((c) => ({
      time: c.time as unknown as CandlestickData["time"],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    candleSeries.setData(candleData);

    // --- Volume histogram ---
    const volumeSeries = chart.addHistogramSeries({
      color: "rgba(100,116,139,0.35)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    const volData: HistogramData[] = candles.map((c) => ({
      time: c.time as unknown as HistogramData["time"],
      value: c.volume,
      color: c.close >= c.open ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)",
    }));
    volumeSeries.setData(volData);

    // --- MA20 line ---
    const ma20Series = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const ma20Data: LineData[] = candles
      .filter((c) => c.ma20 !== null)
      .map((c) => ({
        time: c.time as unknown as LineData["time"],
        value: c.ma20 as number,
      }));
    ma20Series.setData(ma20Data);

    // --- MA50 line ---
    const ma50Series = chart.addLineSeries({
      color: "#818cf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    const ma50Data: LineData[] = candles
      .filter((c) => c.ma50 !== null)
      .map((c) => ({
        time: c.time as unknown as LineData["time"],
        value: c.ma50 as number,
      }));
    ma50Series.setData(ma50Data);

    // --- Entry price horizontal line ---
    if (entryPrice) {
      candleSeries.createPriceLine({
        price: entryPrice,
        color: "#22c55e",
        lineWidth: 1,
        lineStyle: 2,          // dashed
        axisLabelVisible: true,
        title: "Entry",
      });
    }

    // --- Stop loss horizontal line ---
    if (stopPrice) {
      candleSeries.createPriceLine({
        price: stopPrice,
        color: "#ef4444",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: "Stop",
      });
    }

    chart.timeScale().fitContent();

    // Resize listener
    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
    };
  }, [candles, entryPrice, stopPrice, height]);

  if (candles.length === 0) {
    return (
      <div style={{ color: "var(--text-muted)", fontSize: "12px", padding: "8px 0" }}>
        No chart data available.
      </div>
    );
  }

  return (
    <div style={{ marginTop: "12px" }}>
      <div style={{ display: "flex", gap: "12px", fontSize: "11px", color: "#94a3b8", marginBottom: "4px" }}>
        <span style={{ color: "#f59e0b" }}>— MA20</span>
        <span style={{ color: "#818cf8" }}>— MA50</span>
        {entryPrice && <span style={{ color: "#22c55e" }}>-- Entry</span>}
        {stopPrice && <span style={{ color: "#ef4444" }}>-- Stop</span>}
      </div>
      <div ref={containerRef} style={{ width: "100%", height: `${height}px` }} />
    </div>
  );
}
```

### Step 3.2 — Commit

```bash
git add frontend/app/components/CandleChart.tsx
git commit -m "feat(ui): add shared CandleChart component"
```

---

## Task 4: Embed chart in `CandidateDetailPanel` (Dashboard)

**Files:**
- Modify: `frontend/app/dashboard-client.tsx`

### Step 4.1 — Add state and fetch logic to `CandidateDetailPanel`

`CandidateDetailPanel` already receives `item`, `accountSize`, `apiBaseUrl`, and `date`. We need to add `useEffect` to fetch OHLCV whenever `item` changes, store it in state, and render `<CandleChart>` below the existing metrics.

Replace the `CandidateDetailPanel` function body. The key additions are:

```tsx
// At top of file, add import:
import CandleChart, { type Candle } from "./components/CandleChart";

// Inside CandidateDetailPanel, add new state after the existing useState calls:
const [candles, setCandles] = useState<Candle[]>([]);
const [chartLoading, setChartLoading] = useState(false);

// After the existing useEffect([item]), add a new effect:
useEffect(() => {
  if (!item) { setCandles([]); return; }
  setChartLoading(true);
  fetch(`${apiBaseUrl}/ohlcv/${item.symbol}?days=90`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((data) => setCandles(data.candles ?? []))
    .catch(() => setCandles([]))
    .finally(() => setChartLoading(false));
}, [item, apiBaseUrl]);
```

Inside the non-executing view (not the form), add the chart BELOW the `.notesBox` div:

```tsx
{chartLoading ? (
  <div style={{ fontSize: "11px", color: "var(--text-muted)", paddingTop: "8px" }}>
    Loading chart…
  </div>
) : (
  <CandleChart candles={candles} height={240} />
)}
```

> The executing form (`isExecuting === true`) should also show the chart. Add the same `<CandleChart>` block **before** the form's closing `</form>` closing div:
```tsx
<CandleChart candles={candles} entryPrice={entryPrice} stopPrice={stopValue > 0 ? stopValue : undefined} height={240} />
```

### Step 4.2 — Build to verify TypeScript

```powershell
cd d:\antigravity\Dhanustambha\frontend
npm run build
```
Expected: `Exit code: 0`.

### Step 4.3 — Commit

```bash
git add frontend/app/dashboard-client.tsx
git commit -m "feat(ui): embed candlechart in candidate detail panel"
```

---

## Task 5: Embed chart in Trade Book (`trade-client.tsx`)

**Files:**
- Modify: `frontend/app/trades/trade-client.tsx`

### Step 5.1 — Add selected symbol state and chart fetch

When the user clicks **Modify Stop** or **Close**, we already set `activeTrade`. We should also fetch chart data for that trade. Add at the top of `TradeClient`:

```tsx
import CandleChart, { type Candle } from "../components/CandleChart";

// New state inside TradeClient:
const [chartCandles, setChartCandles] = useState<Candle[]>([]);
const [chartLoading, setChartLoading] = useState(false);
```

Modify `handleActionClick` to also fetch chart data:

```tsx
function handleActionClick(trade: Trade, mode: "UPDATE_STOP" | "CLOSE") {
  setActiveTrade(trade);
  setActionMode(mode);
  setNewStop(trade.stop_price ? trade.stop_price.toString() : "");
  setClosePrice(trade.current_close ? trade.current_close.toString() : "");
  // fetch chart
  setChartCandles([]);
  setChartLoading(true);
  fetch(`${apiBaseUrl}/ohlcv/${trade.symbol}?days=90`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((data) => setChartCandles(data.candles ?? []))
    .catch(() => setChartCandles([]))
    .finally(() => setChartLoading(false));
}
```

### Step 5.2 — Render chart inside the action form section

Inside the `{activeTrade && actionMode && (…)}` panel, render the chart **after** the action `<form>`:

```tsx
{chartLoading ? (
  <div style={{ fontSize: "11px", color: "var(--text-muted)", paddingTop: "12px" }}>
    Loading chart…
  </div>
) : (
  <CandleChart
    candles={chartCandles}
    entryPrice={activeTrade.entry_price}
    stopPrice={actionMode === "UPDATE_STOP" ? Number(newStop) || activeTrade.stop_price : activeTrade.stop_price}
    height={260}
  />
)}
```

### Step 5.3 — Build to verify TypeScript

```powershell
cd d:\antigravity\Dhanustambha\frontend
npm run build
```
Expected: `Exit code: 0`.

### Step 5.4 — Commit

```bash
git add frontend/app/trades/trade-client.tsx
git commit -m "feat(ui): embed candlechart in trade book action panel"
```

---

## Verification Plan

### Automated Tests

Run the full backend API suite:
```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py -v
```
All tests including `test_ohlcv_endpoint_returns_candles_and_ma` must pass.

Run full test suite:
```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests/ -v --ignore=tests/test_backtest.py
```
(The `test_backtest.py` failure is a pre-existing known issue documented in AGENTS.md §12.)

Run the Next.js production build:
```powershell
cd d:\antigravity\Dhanustambha\frontend && npm run build
```
Expected: `Exit code: 0`, both `/` and `/trades` routes compiled.

### Manual Visual Verification

Start the backend and frontend:
```powershell
# Terminal 1 (WSL or PowerShell from project root)
& "C:\Program Files\Python312\python.exe" -m uvicorn src.api.main:app --reload

# Terminal 2
cd d:\antigravity\Dhanustambha\frontend && npm run dev
```

1. Open `http://localhost:3000`. Click any watchlist row — a candlestick chart with MA20 (amber), MA50 (indigo) should appear **below** the existing metrics in the right panel, with no existing content removed.
2. Click **Execute ⚡** on any row — the chart should still be visible inside the execution form, and automatically draw a green **Entry** dashed line and a red **Stop** dashed line as you type the stop price.
3. Navigate to `http://localhost:3000/trades`. Click **Modify Stop** on any open trade — a chart for that symbol should appear below the action form with entry and stop lines overlaid.
4. Resize the browser window — charts should resize fluidly.
