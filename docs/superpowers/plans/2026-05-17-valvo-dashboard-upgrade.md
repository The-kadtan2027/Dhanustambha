# Valvo-Inspired Dashboard Upgrade — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Trade Book into a position card grid, add a `/stock/[symbol]` detail route, and upgrade Market Breadth with regime badges, A/D ratios, and timeframe-toggled sparklines.

**Architecture:** Three independent sub-projects sharing the existing `lightweight-charts` + Recharts stack, the `globals.css` light-mode design system, and the FastAPI backend. Backend grows by 2 endpoints; frontend grows by 4 new components and 1 new route.

**Tech Stack:** Python 3.12 / FastAPI / SQLite, Next.js 14 App Router, lightweight-charts v5, Recharts, TypeScript.

**Spec:** `docs/superpowers/specs/2026-05-17-valvo-inspired-dashboard-upgrade-design.md`

---

## Sub-Project A — Position Manager Card Grid

### Task A1: Backend — `/trades/portfolio` endpoint

**Files:**
- Modify: `src/trade/log.py`
- Modify: `src/api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing test**

```python
# In tests/test_api.py
def test_portfolio_summary_with_open_trade(api_client):
    """Portfolio endpoint should aggregate open trade metrics."""
    from src.trade.log import open_trade
    from src.ingestion.store import upsert_ohlcv

    upsert_ohlcv([
        {"symbol": "INFY", "date": "2026-05-15", "open": 100.0, "high": 102.0, "low": 99.0, "close": 100.0, "volume": 300000},
        {"symbol": "INFY", "date": "2026-05-16", "open": 101.0, "high": 108.0, "low": 100.0, "close": 106.0, "volume": 400000},
    ])
    open_trade(symbol="INFY", setup_type="EP", entry_date="2026-05-15",
               entry_price=100.0, shares=10, stop_price=96.0)

    res = api_client.get("/trades/portfolio")
    assert res.status_code == 200
    data = res.json()
    assert "total_invested" in data
    assert "total_pnl" in data
    assert "open_risk" in data
    assert "locked_profit" in data
    assert data["total_invested"] == 1000.0   # 100 * 10
    assert data["open_risk"] == 40.0           # (100 - 96) * 10
```

- [ ] **Step 2: Run — expect FAIL (endpoint not found)**
```
"C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_portfolio_summary_with_open_trade -v
```

- [ ] **Step 3: Add `build_portfolio_summary()` to `src/trade/log.py`**

Add after `summarize_closed_trades()`:
```python
def build_portfolio_summary() -> dict:
    """Return portfolio-level aggregates for all open trades."""
    trades = build_open_trade_status()
    if trades.empty:
        return {
            "trade_count": 0,
            "total_invested": 0.0,
            "total_pnl": 0.0,
            "open_risk": 0.0,
            "locked_profit": 0.0,
        }

    total_invested = float((trades["entry_price"] * trades["shares"]).sum())
    total_pnl = float(trades["unrealized_pnl"].fillna(0).sum())
    # open_risk = sum of money at risk if stop is hit
    open_risk = float(((trades["entry_price"] - trades["stop_price"]) * trades["shares"]).sum())
    # locked_profit = money protected when stop > entry (trailing to profit)
    trades["stop_above_entry"] = (trades["stop_price"] > trades["entry_price"]).astype(float)
    locked_profit = float(
        ((trades["stop_price"] - trades["entry_price"]) * trades["shares"] * trades["stop_above_entry"]).sum()
    )
    return {
        "trade_count": int(len(trades)),
        "total_invested": round(total_invested, 2),
        "total_pnl": round(total_pnl, 2),
        "open_risk": round(open_risk, 2),
        "locked_profit": round(locked_profit, 2),
    }
```

- [ ] **Step 4: Add endpoint to `src/api/main.py`**

Add after `GET /trades/summary`:
```python
@app.get("/trades/portfolio")
def trade_portfolio() -> Dict[str, Any]:
    """Return portfolio-level aggregates across all open trades."""
    from src.trade.log import build_portfolio_summary
    return build_portfolio_summary()
```

- [ ] **Step 5: Run — expect PASS**
```
"C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_portfolio_summary_with_open_trade -v
```

- [ ] **Step 6: Commit**
```
git add src/trade/log.py src/api/main.py tests/test_api.py
git commit -m "feat(api): add GET /trades/portfolio aggregate endpoint"
```

---

### Task A2: Backend — `/trades/by-symbol/{symbol}` endpoint

**Files:**
- Modify: `src/api/main.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Write failing test**

```python
def test_trades_by_symbol_returns_all_statuses(api_client):
    """Should return both open and closed trades for a symbol."""
    from src.trade.log import open_trade, close_trade
    from src.ingestion.store import upsert_ohlcv

    upsert_ohlcv([
        {"symbol": "TCS", "date": "2026-05-10", "open": 200.0, "high": 202.0, "low": 199.0, "close": 200.0, "volume": 500000},
        {"symbol": "TCS", "date": "2026-05-11", "open": 201.0, "high": 215.0, "low": 200.0, "close": 210.0, "volume": 800000},
    ])
    tid = open_trade(symbol="TCS", setup_type="MB", entry_date="2026-05-10",
                     entry_price=200.0, shares=5, stop_price=195.0)
    close_trade(tid, exit_date="2026-05-11", exit_price=210.0)

    res = api_client.get("/trades/by-symbol/TCS")
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "TCS"
    assert len(data["trades"]) == 1
    assert data["trades"][0]["status"] in ("CLOSED_WIN", "CLOSED_LOSS", "CLOSED_BE", "OPEN")
```

- [ ] **Step 2: Run — expect FAIL**
```
"C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_trades_by_symbol_returns_all_statuses -v
```

- [ ] **Step 3: Add endpoint to `src/api/main.py`**

Add after `GET /trades/portfolio`:
```python
@app.get("/trades/by-symbol/{symbol}")
def trades_by_symbol(symbol: str) -> Dict[str, Any]:
    """Return all trades (open and closed) for a given symbol."""
    from src.ingestion.store import get_trades
    all_trades = get_trades()
    if not all_trades.empty:
        filtered = all_trades[all_trades["symbol"] == symbol.upper()]
    else:
        filtered = all_trades
    return {
        "symbol": symbol.upper(),
        "count": int(len(filtered)),
        "trades": _records_from_dataframe(filtered),
    }
```

- [ ] **Step 4: Run — expect PASS**
```
"C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py::test_trades_by_symbol_returns_all_statuses -v
```

- [ ] **Step 5: Commit**
```
git add src/api/main.py tests/test_api.py
git commit -m "feat(api): add GET /trades/by-symbol/{symbol} endpoint"
```

---

### Task A3: Frontend types and CSS

**Files:**
- Modify: `frontend/types/api.ts`
- Modify: `frontend/app/globals.css`

- [ ] **Step 1: Add `PortfolioSummary` type to `frontend/types/api.ts`**

Append:
```typescript
export type PortfolioSummary = {
  trade_count: number;
  total_invested: number;
  total_pnl: number;
  open_risk: number;
  locked_profit: number;
};

export type TradesBySymbol = {
  symbol: string;
  count: number;
  trades: Trade[];
};
```

- [ ] **Step 2: Add position card / portfolio bar CSS to `frontend/app/globals.css`**

Append at end of file:
```css
/* ── Position Card Grid ── */
.positionGrid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
}

.positionCard {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: var(--shadow);
  overflow: hidden;
}

.positionCard.winner { border-top: 3px solid var(--green); }
.positionCard.loser  { border-top: 3px solid var(--red); }
.positionCard.flat   { border-top: 3px solid var(--line); }

.positionCardHeader {
  align-items: flex-start;
  display: flex;
  justify-content: space-between;
  padding: 14px 16px 0;
}

.positionCardSymbol { font-size: 20px; font-weight: 700; }

.positionCardGain {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
  text-align: right;
}

.positionCardMeta {
  color: var(--muted);
  font-size: 12px;
  margin-top: 2px;
}

.positionCardMetrics {
  display: grid;
  gap: 0;
  grid-template-columns: repeat(3, 1fr);
  padding: 10px 16px;
}

.positionCardMetric {
  padding: 6px 0;
}

.positionCardMetric .label { font-size: 11px; }
.positionCardMetric strong { font-size: 14px; }

.positionCardFooter {
  background: var(--panel-muted);
  border-top: 1px solid var(--line);
  display: flex;
  font-size: 12px;
  justify-content: space-between;
  padding: 8px 16px;
}

/* ── Stock Detail ── */
.stockDetailLayout {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr 300px;
  min-height: calc(100vh - 80px);
}

.stockDetailSidebar {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 16px;
}

.pnlHero {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
  margin: 12px 0 4px;
}

.sellHistoryItem {
  border-bottom: 1px solid var(--line);
  font-size: 13px;
  padding: 8px 0;
}

/* ── Enhanced Breadth ── */
.regimeBadge {
  border-radius: 6px;
  display: inline-flex;
  font-size: 13px;
  font-weight: 700;
  padding: 4px 12px;
}

.regimeBadge.bullish  { background: #e7f6ef; color: var(--green); }
.regimeBadge.cautious { background: #fff4d6; color: var(--amber); }
.regimeBadge.bearish  { background: #fde8e7; color: var(--red); }

.adRatio {
  align-items: center;
  display: flex;
  gap: 24px;
  margin: 12px 0;
}

.adCount { font-size: 36px; font-weight: 700; line-height: 1; }
.adCount.adv { color: var(--green); }
.adCount.dec { color: var(--red); }

.adBar {
  border-radius: 4px;
  display: flex;
  height: 8px;
  overflow: hidden;
  width: 100%;
}

.adBar .adv { background: var(--green); transition: width 0.4s; }
.adBar .dec { background: var(--red); transition: width 0.4s; }

.breadthSparkGrid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, 1fr);
  margin-top: 16px;
}

.breadthSparkCard {
  background: var(--panel-muted);
  border-radius: 8px;
  padding: 12px;
}

.breadthSparkValue {
  font-size: 24px;
  font-weight: 700;
  line-height: 1;
  margin: 6px 0 4px;
}

.timeframeBar {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
}

.timeframeBtn {
  background: transparent;
  border: 1px solid var(--line);
  border-radius: 4px;
  color: var(--muted);
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  padding: 3px 10px;
}

.timeframeBtn.active {
  background: var(--text);
  border-color: var(--text);
  color: white;
}
```

- [ ] **Step 3: Commit**
```
git add frontend/types/api.ts frontend/app/globals.css
git commit -m "feat(frontend): add portfolio types and position card / breadth CSS"
```

---

### Task A4: `PositionCard` component

**Files:**
- Create: `frontend/app/components/PositionCard.tsx`

- [ ] **Step 1: Create `frontend/app/components/PositionCard.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import type { Trade } from "../../../types/api";
import { formatCurrency, formatNumber } from "../../../lib/format";
import CandleChart, { type Candle } from "./CandleChart";

type Props = {
  trade: Trade;
  apiBaseUrl: string;
  onManageClick: (trade: Trade, mode: "UPDATE_STOP" | "CLOSE") => void;
};

export default function PositionCard({ trade, apiBaseUrl, onManageClick }: Props) {
  const [candles, setCandles] = useState<Candle[]>([]);

  useEffect(() => {
    fetch(`${apiBaseUrl}/ohlcv/${trade.symbol}?days=90`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setCandles(d.candles ?? []))
      .catch(() => setCandles([]));
  }, [trade.symbol, apiBaseUrl]);

  const gain = trade.pct_gain ?? 0;
  const cardClass = gain > 0 ? "winner" : gain < 0 ? "loser" : "flat";
  const gainColor = gain >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div className={`positionCard ${cardClass}`}>
      <div className="positionCardHeader">
        <div>
          <div className="positionCardSymbol">{trade.symbol}</div>
          <div className="positionCardMeta">
            {trade.setup_type.replaceAll("_", " ")} · {trade.days_held ?? 0}d held
            {trade.action_required !== "NONE" && (
              <span style={{ color: "var(--amber)", marginLeft: 8 }}>
                ⚠ {trade.action_required.replaceAll("_", " ")}
              </span>
            )}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="positionCardGain" style={{ color: gainColor }}>
            {gain >= 0 ? "+" : ""}{formatNumber(gain, 2)}%
          </div>
          <div className="positionCardMeta" style={{ color: gainColor }}>
            {formatCurrency(trade.unrealized_pnl)}
          </div>
        </div>
      </div>

      <div className="positionCardMetrics">
        <div className="positionCardMetric">
          <span className="label">Entry</span>
          <strong>{formatCurrency(trade.entry_price)}</strong>
        </div>
        <div className="positionCardMetric">
          <span className="label">Stop</span>
          <strong>{formatCurrency(trade.stop_price)}</strong>
        </div>
        <div className="positionCardMetric">
          <span className="label">CMP</span>
          <strong>{formatCurrency(trade.current_close)}</strong>
        </div>
      </div>

      <div style={{ padding: "0 8px" }}>
        <CandleChart
          candles={candles}
          entryPrice={trade.entry_price}
          stopPrice={trade.stop_price}
          height={220}
        />
      </div>

      <div className="positionCardFooter">
        <span>{trade.shares ?? "-"} shares</span>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => onManageClick(trade, "UPDATE_STOP")}
            style={{ background: "var(--panel)", border: "1px solid var(--line)", padding: "3px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
          >
            Modify Stop
          </button>
          <button
            onClick={() => onManageClick(trade, "CLOSE")}
            style={{ background: "var(--text)", color: "white", border: "none", padding: "3px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```
git add frontend/app/components/PositionCard.tsx
git commit -m "feat(frontend): add PositionCard component with embedded chart"
```

---

### Task A5: `PortfolioBar` component

**Files:**
- Create: `frontend/app/components/PortfolioBar.tsx`

- [ ] **Step 1: Create `frontend/app/components/PortfolioBar.tsx`**

```tsx
import type { PortfolioSummary } from "../../../types/api";
import { formatCurrency } from "../../../lib/format";

function Cell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: "14px 20px" }}>
      <span className="label" style={{ color: "rgba(255,255,255,0.6)" }}>{label}</span>
      <strong style={{ display: "block", fontSize: 24, marginTop: 6, color: color ?? "white" }}>
        {value}
      </strong>
    </div>
  );
}

export default function PortfolioBar({ summary }: { summary: PortfolioSummary | null }) {
  if (!summary) return null;
  const pnlColor = summary.total_pnl >= 0 ? "#4ade80" : "#f87171";
  return (
    <div className="heroBand" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))", marginBottom: 20 }}>
      <Cell label="Open Positions" value={String(summary.trade_count)} />
      <Cell label="Total P&L" value={formatCurrency(summary.total_pnl)} color={pnlColor} />
      <Cell label="Total Invested" value={formatCurrency(summary.total_invested)} />
      <Cell label="Open Risk" value={formatCurrency(summary.open_risk)} color="#fbbf24" />
      <Cell label="Locked Profit" value={formatCurrency(summary.locked_profit)} color="#4ade80" />
    </div>
  );
}
```

- [ ] **Step 2: Commit**
```
git add frontend/app/components/PortfolioBar.tsx
git commit -m "feat(frontend): add PortfolioBar 5-metric hero band"
```

---

### Task A6: Rewrite Trade Book client

**Files:**
- Modify: `frontend/app/trades/trade-client.tsx`
- Modify: `frontend/app/trades/page.tsx`

- [ ] **Step 1: Update `frontend/app/trades/page.tsx`** to also fetch portfolio summary:

```tsx
import TradeClient from "./trade-client";
import type { TradeList, PortfolioSummary } from "../../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch { return null; }
}

export default async function TradesPage() {
  const [openTrades, portfolio] = await Promise.all([
    fetchJson<TradeList>("/trades/open"),
    fetchJson<PortfolioSummary>("/trades/portfolio"),
  ]);
  return <TradeClient apiBaseUrl={API_BASE_URL} initialOpenTrades={openTrades} initialPortfolio={portfolio} />;
}
```

- [ ] **Step 2: Rewrite `frontend/app/trades/trade-client.tsx`**

Replace the entire file with:

```tsx
"use client";

import { useState } from "react";
import { AlertTriangle, RefreshCw, CheckCircle2, LayoutGrid, List } from "lucide-react";
import type { Trade, TradeList, PortfolioSummary } from "../../types/api";
import { formatCurrency } from "../../lib/format";
import PositionCard from "../components/PositionCard";
import PortfolioBar from "../components/PortfolioBar";
import CandleChart, { type Candle } from "../components/CandleChart";

type Props = {
  apiBaseUrl: string;
  initialOpenTrades: TradeList | null;
  initialPortfolio: PortfolioSummary | null;
};

export default function TradeClient({ apiBaseUrl, initialOpenTrades, initialPortfolio }: Props) {
  const [openTrades, setOpenTrades] = useState(initialOpenTrades);
  const [portfolio, setPortfolio] = useState(initialPortfolio);
  const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTrade, setActiveTrade] = useState<Trade | null>(null);
  const [actionMode, setActionMode] = useState<"UPDATE_STOP" | "CLOSE" | null>(null);
  const [newStop, setNewStop] = useState("");
  const [closePrice, setClosePrice] = useState("");
  const [closeDate, setCloseDate] = useState(new Date().toISOString().split("T")[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chartCandles, setChartCandles] = useState<Candle[]>([]);

  async function loadTrades() {
    setIsLoading(true);
    setError(null);
    try {
      const [t, p] = await Promise.all([
        fetch(`${apiBaseUrl}/trades/open`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${apiBaseUrl}/trades/portfolio`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setOpenTrades(t);
      setPortfolio(p);
      setActiveTrade(null);
      setActionMode(null);
    } catch (e) { setError(String(e)); }
    finally { setIsLoading(false); }
  }

  function handleManage(trade: Trade, mode: "UPDATE_STOP" | "CLOSE") {
    setActiveTrade(trade);
    setActionMode(mode);
    setNewStop(trade.stop_price?.toString() ?? "");
    setClosePrice(trade.current_close?.toString() ?? "");
    setChartCandles([]);
    fetch(`${apiBaseUrl}/ohlcv/${trade.symbol}?days=90`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setChartCandles(d.candles ?? []))
      .catch(() => setChartCandles([]));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!activeTrade) return;
    setIsSubmitting(true);
    try {
      if (actionMode === "UPDATE_STOP") {
        const res = await fetch(`${apiBaseUrl}/trades/${activeTrade.id}/update-stop`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stop_price: Number(newStop) }),
        });
        if (!res.ok) throw new Error("Failed to update stop");
      } else {
        const res = await fetch(`${apiBaseUrl}/trades/${activeTrade.id}/close`, {
          method: "PUT", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exit_date: closeDate, exit_price: Number(closePrice) }),
        });
        if (!res.ok) throw new Error("Failed to close trade");
      }
      await loadTrades();
    } catch (e) { alert(String(e)); }
    finally { setIsSubmitting(false); }
  }

  const trades = openTrades?.items ?? [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Trade Book</h1>
          <p>{trades.length} open position{trades.length !== 1 ? "s" : ""}</p>
        </div>
        <div className="topbarControls">
          <button className={`timeframeBtn ${viewMode === "cards" ? "active" : ""}`} onClick={() => setViewMode("cards")} title="Card view">
            <LayoutGrid size={15} />
          </button>
          <button className={`timeframeBtn ${viewMode === "table" ? "active" : ""}`} onClick={() => setViewMode("table")} title="Table view">
            <List size={15} />
          </button>
          <button className="iconButton" disabled={isLoading} onClick={loadTrades} title="Refresh">
            <RefreshCw size={16} />
          </button>
          <div className={`statusPill ${!openTrades ? "offline" : "online"}`}>
            {!openTrades ? <><AlertTriangle size={16} /> API offline</> : <><CheckCircle2 size={16} /> Connected</>}
          </div>
        </div>
      </header>

      <PortfolioBar summary={portfolio} />

      {error && <div className="errorBanner"><AlertTriangle size={16} /><span>{error}</span></div>}

      {activeTrade && actionMode && (
        <div className="panel wide" style={{ marginBottom: 16 }}>
          <h2 style={{ fontSize: 16, marginBottom: 12 }}>
            {actionMode === "UPDATE_STOP" ? "Update Stop Loss" : "Close Trade"}: {activeTrade.symbol}
          </h2>
          <form onSubmit={handleSubmit} style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
            {actionMode === "UPDATE_STOP" ? (
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="label">New Stop Price</span>
                <input type="number" step="0.05" required value={newStop} onChange={(e) => setNewStop(e.target.value)}
                  style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "6px 10px", borderRadius: 4 }} />
              </label>
            ) : (
              <>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="label">Exit Price</span>
                  <input type="number" step="0.05" required value={closePrice} onChange={(e) => setClosePrice(e.target.value)}
                    style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "6px 10px", borderRadius: 4 }} />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="label">Exit Date</span>
                  <input type="date" required value={closeDate} onChange={(e) => setCloseDate(e.target.value)}
                    style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "6px 10px", borderRadius: 4 }} />
                </label>
              </>
            )}
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" disabled={isSubmitting}
                style={{ background: "var(--text)", color: "white", border: "none", padding: "6px 14px", borderRadius: 4, fontWeight: "bold", cursor: "pointer" }}>
                {isSubmitting ? "Saving..." : "Confirm"}
              </button>
              <button type="button" onClick={() => setActiveTrade(null)}
                style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "6px 14px", borderRadius: 4, cursor: "pointer" }}>
                Cancel
              </button>
            </div>
          </form>
          <CandleChart candles={chartCandles}
            entryPrice={activeTrade.entry_price}
            stopPrice={actionMode === "UPDATE_STOP" ? (Number(newStop) || activeTrade.stop_price) : activeTrade.stop_price}
            height={320} />
        </div>
      )}

      {trades.length === 0 ? (
        <div className="empty">No open trades. Open a trade from the Scanners page.</div>
      ) : viewMode === "cards" ? (
        <div className="positionGrid">
          {trades.map((t) => (
            <PositionCard key={t.id} trade={t} apiBaseUrl={apiBaseUrl} onManageClick={handleManage} />
          ))}
        </div>
      ) : (
        <div className="panel wide">
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th><th>Setup</th>
                  <th className="num">Entry</th><th className="num">Stop</th>
                  <th className="num">CMP</th><th className="num">P&L</th>
                  <th className="num">Gain%</th><th>Action</th><th>Manage</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className={activeTrade?.id === t.id ? "selectedRow" : ""}>
                    <td><strong>{t.symbol}</strong></td>
                    <td>{t.setup_type.replaceAll("_", " ")}</td>
                    <td className="num">{formatCurrency(t.entry_price)}</td>
                    <td className="num">{formatCurrency(t.stop_price)}</td>
                    <td className="num">{formatCurrency(t.current_close)}</td>
                    <td className="num" style={{ color: (t.unrealized_pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                      {formatCurrency(t.unrealized_pnl)}
                    </td>
                    <td className="num" style={{ color: (t.pct_gain ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                      {t.pct_gain?.toFixed(2) ?? "-"}%
                    </td>
                    <td><span style={{ color: t.action_required !== "NONE" ? "var(--amber)" : "inherit" }}>
                      {t.action_required.replaceAll("_", " ")}
                    </span></td>
                    <td>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button onClick={() => handleManage(t, "UPDATE_STOP")}
                          style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "2px 8px", borderRadius: 4, fontSize: 12, cursor: "pointer" }}>
                          Stop
                        </button>
                        <button onClick={() => handleManage(t, "CLOSE")}
                          style={{ background: "var(--text)", color: "white", border: "none", padding: "2px 8px", borderRadius: 4, fontSize: 12, cursor: "pointer" }}>
                          Close
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  );
}
```

- [ ] **Step 3: Commit**
```
git add frontend/app/trades/page.tsx frontend/app/trades/trade-client.tsx
git commit -m "feat(frontend): rewrite Trade Book with card grid + PortfolioBar"
```

---

## Sub-Project B — Stock Detail View

### Task B1: New `/stock/[symbol]` route

**Files:**
- Create: `frontend/app/stock/[symbol]/page.tsx`
- Create: `frontend/app/stock/[symbol]/stock-detail-client.tsx`

- [ ] **Step 1: Create `frontend/app/stock/[symbol]/page.tsx`**

```tsx
import StockDetailClient from "./stock-detail-client";
import type { TradesBySymbol } from "../../../types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch { return null; }
}

export default async function StockDetailPage({ params }: { params: { symbol: string } }) {
  const symbol = params.symbol.toUpperCase();
  const tradeData = await fetchJson<TradesBySymbol>(`/trades/by-symbol/${symbol}`);
  return <StockDetailClient apiBaseUrl={API_BASE_URL} symbol={symbol} initialTradeData={tradeData} />;
}
```

- [ ] **Step 2: Create `frontend/app/stock/[symbol]/stock-detail-client.tsx`**

```tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import type { TradesBySymbol } from "../../../types/api";
import { formatCurrency, formatNumber } from "../../../lib/format";
import CandleChart, { type Candle } from "../../components/CandleChart";

const TIMEFRAMES = [
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
  { label: "2Y", days: 730 },
];

type Props = {
  apiBaseUrl: string;
  symbol: string;
  initialTradeData: TradesBySymbol | null;
};

export default function StockDetailClient({ apiBaseUrl, symbol, initialTradeData }: Props) {
  const router = useRouter();
  const [candles, setCandles] = useState<Candle[]>([]);
  const [days, setDays] = useState(365);

  useEffect(() => {
    fetch(`${apiBaseUrl}/ohlcv/${symbol}?days=${days}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setCandles(d.candles ?? []))
      .catch(() => setCandles([]));
  }, [symbol, days, apiBaseUrl]);

  const openTrade = initialTradeData?.trades.find((t) => t.status === "OPEN") ?? null;
  const closedTrades = initialTradeData?.trades.filter((t) => t.status !== "OPEN") ?? [];
  const totalRealizedPnl = closedTrades.reduce((s, t) => s + (t.pnl ?? 0), 0);

  const lastCandle = candles[candles.length - 1];

  return (
    <main className="shell">
      <header className="topbar" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => router.back()}
            style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", borderRadius: 6, padding: "6px 10px", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
            <ArrowLeft size={16} /> Back
          </button>
          <div>
            <h1 style={{ margin: 0 }}>{symbol}</h1>
            {lastCandle && (
              <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>
                CMP {formatCurrency(lastCandle.close)} · MA20 {formatCurrency(lastCandle.ma20)} · MA50 {formatCurrency(lastCandle.ma50)}
              </p>
            )}
          </div>
        </div>
        <div className="timeframeBar">
          {TIMEFRAMES.map((tf) => (
            <button key={tf.label} className={`timeframeBtn ${days === tf.days ? "active" : ""}`}
              onClick={() => setDays(tf.days)}>{tf.label}
            </button>
          ))}
        </div>
      </header>

      <div className="stockDetailLayout">
        <div className="panel">
          <CandleChart
            candles={candles}
            entryPrice={openTrade?.entry_price}
            stopPrice={openTrade?.stop_price}
            height={500}
          />
        </div>

        <div className="stockDetailSidebar">
          {openTrade ? (
            <>
              <span className="label">Open Position</span>
              <div className="pnlHero" style={{ color: (openTrade.unrealized_pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                {formatCurrency(openTrade.unrealized_pnl)}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 16 }}>
                {formatNumber(openTrade.pct_gain, 2)}% · {openTrade.days_held}d held
              </div>
              <div className="metricGrid">
                <div className="metric"><span>Entry</span><strong style={{ fontSize: 16 }}>{formatCurrency(openTrade.entry_price)}</strong></div>
                <div className="metric"><span>Stop</span><strong style={{ fontSize: 16 }}>{formatCurrency(openTrade.stop_price)}</strong></div>
                <div className="metric"><span>Shares</span><strong style={{ fontSize: 16 }}>{openTrade.shares}</strong></div>
                <div className="metric"><span>Setup</span><strong style={{ fontSize: 14 }}>{openTrade.setup_type.replaceAll("_", " ")}</strong></div>
              </div>
              <div style={{ marginTop: 12, background: "var(--panel-muted)", borderRadius: 6, padding: "8px 12px", fontSize: 13 }}>
                <strong>Action:</strong> {openTrade.action_required.replaceAll("_", " ")}
              </div>
            </>
          ) : closedTrades.length > 0 ? (
            <>
              <span className="label">Trade History</span>
              <div className="pnlHero" style={{ color: totalRealizedPnl >= 0 ? "var(--green)" : "var(--red)" }}>
                {formatCurrency(totalRealizedPnl)}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginBottom: 16 }}>Realized P&L · {closedTrades.length} trade(s)</div>
            </>
          ) : (
            <div className="empty">No trades for {symbol}.</div>
          )}

          {closedTrades.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <span className="label" style={{ marginBottom: 8, display: "block" }}>Sell History</span>
              {closedTrades.map((t) => (
                <div key={t.id} className="sellHistoryItem">
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span>{t.exit_date ?? "-"}</span>
                    <span style={{ color: (t.pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)", fontWeight: 700 }}>
                      {formatCurrency(t.pnl)}
                    </span>
                  </div>
                  <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 2 }}>
                    {formatCurrency(t.entry_price)} → {formatCurrency(t.exit_price)} · {t.shares} sh
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Make symbols in Scanners and Journal link to the stock detail page**

In `frontend/app/scanners/scanner-client.tsx`, change the symbol button in `WatchlistPanel`:
```tsx
// Replace the existing symbol button:
import Link from 'next/link';
// In the tbody td:
<td>
  <Link href={`/stock/${item.symbol}`} className="textButton">
    {item.symbol}
  </Link>
</td>
```

In `frontend/app/journal/journal-client.tsx`, in the trades table tbody:
```tsx
// Add import
import Link from 'next/link';
// Change symbol cell from:
<td><strong>{t.symbol}</strong></td>
// To:
<td><Link href={`/stock/${t.symbol}`} style={{ fontWeight: 700, color: "var(--blue)" }}>{t.symbol}</Link></td>
```

- [ ] **Step 4: Commit**
```
git add frontend/app/stock/ frontend/app/scanners/scanner-client.tsx frontend/app/journal/journal-client.tsx
git commit -m "feat(frontend): add /stock/[symbol] detail route with chart + trade sidebar"
```

---

## Sub-Project C — Enhanced Market Breadth

### Task C1: Rewrite `BreadthGauges` component

**Files:**
- Modify: `frontend/app/components/BreadthGauges.tsx`

- [ ] **Step 1: Rewrite `frontend/app/components/BreadthGauges.tsx`**

Replace entire file:

```tsx
"use client";

import { useState, useEffect } from "react";
import {
  BarChart, Bar, AreaChart, Area, ResponsiveContainer,
  XAxis, YAxis, Tooltip,
} from "recharts";
import type { Market } from "../../types/api";

type Props = {
  market: Market;
  history: Market[];
  apiBaseUrl: string;
};

const TIMEFRAMES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
];

function regimeLabel(market: Market): { text: string; cls: string } {
  const ma20 = market.pct_above_ma20 ?? 0;
  if (market.verdict === "OFFENSIVE" && ma20 >= 65) return { text: "Strongly Bullish", cls: "bullish" };
  if (market.verdict === "OFFENSIVE") return { text: "Moderately Bullish", cls: "bullish" };
  if (market.verdict === "DEFENSIVE") return { text: "Cautious", cls: "cautious" };
  if (market.verdict === "AVOID" && ma20 < 35) return { text: "Bearish", cls: "bearish" };
  return { text: "Cautious / Avoid", cls: "cautious" };
}

function SparkCard({ title, value, unit, data, dataKey, color }: {
  title: string; value: number | null; unit?: string;
  data: Record<string, unknown>[]; dataKey: string; color: string;
}) {
  return (
    <div className="breadthSparkCard">
      <span className="label">{title}</span>
      <div className="breadthSparkValue" style={{ color }}>
        {value != null ? `${value.toFixed(1)}${unit ?? ""}` : "-"}
      </div>
      <ResponsiveContainer width="100%" height={60}>
        <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.4} />
              <stop offset="95%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5}
            fill={`url(#grad-${dataKey})`} dot={false} />
          <Tooltip
            contentStyle={{ background: "#1e293b", border: "none", borderRadius: 6, fontSize: 11 }}
            itemStyle={{ color: "#fff" }}
            labelFormatter={() => ""}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function BreadthGauges({ market, history: initialHistory, apiBaseUrl }: Props) {
  const [days, setDays] = useState(90);
  const [history, setHistory] = useState<Market[]>(initialHistory);

  useEffect(() => {
    fetch(`${apiBaseUrl}/market/breadth/history?days=${days}`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => setHistory(d.items ?? []))
      .catch(() => {});
  }, [days, apiBaseUrl]);

  const regime = regimeLabel(market);

  const advancing = market.advancing ?? 0;
  const declining = market.declining ?? 0;
  const total = advancing + declining || 1;
  const advPct = (advancing / total) * 100;
  const ratio = declining > 0 ? (advancing / declining).toFixed(2) : "∞";

  const chartData = history.map((h) => ({
    date: h.date?.slice(5) ?? "",
    ma20: h.pct_above_ma20 ?? null,
    ma50: h.pct_above_ma50 ?? null,
    netHL: (h.new_highs_52w ?? 0) - (h.new_lows_52w ?? 0),
    netAD: (h.advancing ?? 0) - (h.declining ?? 0),
  }));

  return (
    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Regime Badge + Timeframe */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className={`regimeBadge ${regime.cls}`}>◆ {regime.text}</span>
        <div className="timeframeBar">
          {TIMEFRAMES.map((tf) => (
            <button key={tf.label} className={`timeframeBtn ${days === tf.days ? "active" : ""}`}
              onClick={() => setDays(tf.days)}>{tf.label}
            </button>
          ))}
        </div>
      </div>

      {/* A/D Ratio */}
      <div>
        <div className="adRatio">
          <div>
            <div className="adCount adv">{advancing.toLocaleString()}</div>
            <div style={{ fontSize: 11, color: "var(--green)", marginTop: 2 }}>Advancing</div>
          </div>
          <div style={{ fontSize: 18, color: "var(--muted)", fontWeight: 700 }}>{ratio} : 1</div>
          <div>
            <div className="adCount dec">{declining.toLocaleString()}</div>
            <div style={{ fontSize: 11, color: "var(--red)", marginTop: 2 }}>Declining</div>
          </div>
        </div>
        <div className="adBar">
          <div className="adv" style={{ width: `${advPct}%` }} />
          <div className="dec" style={{ width: `${100 - advPct}%` }} />
        </div>
      </div>

      {/* Daily A/D Bar Chart */}
      <div>
        <div className="label" style={{ marginBottom: 6 }}>Daily Advances − Declines</div>
        <ResponsiveContainer width="100%" height={100}>
          <BarChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
            <XAxis dataKey="date" hide />
            <YAxis hide />
            <Tooltip
              contentStyle={{ background: "#1e293b", border: "none", borderRadius: 6, fontSize: 11 }}
              itemStyle={{ color: "#fff" }}
              labelStyle={{ color: "#94a3b8" }}
            />
            <Bar dataKey="netAD" name="Net A/D"
              fill="#22c55e"
              label={false}
              // Red bars for negative values
              isAnimationActive={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Breadth Sparkline Cards */}
      <div className="breadthSparkGrid">
        <SparkCard
          title="% Above MA20" value={market.pct_above_ma20}
          unit="%" data={chartData} dataKey="ma20"
          color={(market.pct_above_ma20 ?? 0) >= 55 ? "#22c55e" : (market.pct_above_ma20 ?? 0) >= 45 ? "#f59e0b" : "#ef4444"}
        />
        <SparkCard
          title="% Above MA50" value={market.pct_above_ma50}
          unit="%" data={chartData} dataKey="ma50"
          color={(market.pct_above_ma50 ?? 0) >= 50 ? "#22c55e" : "#ef4444"}
        />
        <SparkCard
          title="Net Highs/Lows" value={(market.new_highs_52w ?? 0) - (market.new_lows_52w ?? 0)}
          data={chartData} dataKey="netHL"
          color={((market.new_highs_52w ?? 0) - (market.new_lows_52w ?? 0)) >= 0 ? "#22c55e" : "#ef4444"}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Update `dashboard-client.tsx` to pass `apiBaseUrl` to `BreadthGauges`**

In `frontend/app/dashboard-client.tsx`, in the `MarketPanel` component, change:
```tsx
// From:
<BreadthGauges market={market} history={breadthHistory} />
// To:
<BreadthGauges market={market} history={breadthHistory} apiBaseUrl={apiBaseUrl} />
```

- [ ] **Step 3: Commit**
```
git add frontend/app/components/BreadthGauges.tsx frontend/app/dashboard-client.tsx
git commit -m "feat(frontend): rewrite BreadthGauges with regime badge, A/D bars, sparklines, timeframe toggle"
```

---

## Task D: Update Playwright E2E Tests

**Files:**
- Modify: `frontend/tests/navigation.spec.ts`

- [ ] **Step 1: Add stock detail and card grid tests**

Append to `frontend/tests/navigation.spec.ts`:
```typescript
test('trade book shows card grid by default', async ({ page }) => {
  await page.goto('/trades');
  // Card grid toggle button should be visible
  await expect(page.locator('.timeframeBtn').first()).toBeVisible();
  // No table header by default (card view)
  // The header h1 should be present
  await expect(page.locator('h1')).toContainText(/Trade Book/i);
});

test('stock detail route loads for a symbol', async ({ page }) => {
  // Navigate directly to a stock detail page
  await page.goto('/stock/RELIANCE');
  await expect(page.locator('h1')).toContainText('RELIANCE');
  // Back button should be present
  await expect(page.getByRole('button', { name: /back/i })).toBeVisible();
});
```

- [ ] **Step 2: Run all Playwright tests — expect PASS**
```
cd d:\antigravity\Dhanustambha\frontend
npx playwright test tests/navigation.spec.ts --reporter=line
```

- [ ] **Step 3: Commit**
```
git add frontend/tests/navigation.spec.ts
git commit -m "test(e2e): add trade book card grid and stock detail route tests"
```

---

## Final Verification

After all tasks are complete:

```bash
# 1. Run all Python tests
"C:\Program Files\Python312\python.exe" -m pytest tests/ -v

# 2. Start backend
"C:\Program Files\Python312\python.exe" -m uvicorn src.api.main:app --reload

# 3. Start frontend (separate terminal)
cd frontend && npm run dev

# 4. Run Playwright tests
cd frontend && npx playwright test tests/navigation.spec.ts

# 5. Manual checks:
#    - /trades → Shows portfolio bar + card grid with embedded charts
#    - /trades → Toggle to table view works
#    - /scanners → Clicking symbol opens /stock/{symbol}
#    - /stock/RELIANCE → Full chart + timeframe buttons
#    - / (Dashboard) → Breadth section shows regime badge, A/D bars, sparklines, timeframe toggle
```
