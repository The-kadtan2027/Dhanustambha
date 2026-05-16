"use client";

import { useState } from "react";
import { AlertTriangle, Clock3, RefreshCw, CheckCircle2, TrendingUp, Home } from "lucide-react";
import type { Trade, TradeList } from "../dashboard-client";
import CandleChart, { type Candle } from "../components/CandleChart";

type TradeClientProps = {
  apiBaseUrl: string;
  initialOpenTrades: TradeList | null;
};

function formatCurrency(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "-";
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value);
}

function formatNumber(value: number | null, digits = 1): string {
  if (value === null || Number.isNaN(value)) return "-";
  return value.toFixed(digits);
}

export default function TradeClient({ apiBaseUrl, initialOpenTrades }: TradeClientProps) {
  const [openTrades, setOpenTrades] = useState(initialOpenTrades);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [activeTrade, setActiveTrade] = useState<Trade | null>(null);
  const [actionMode, setActionMode] = useState<"UPDATE_STOP" | "CLOSE" | null>(null);
  
  const [newStop, setNewStop] = useState("");
  const [closePrice, setClosePrice] = useState("");
  const [closeDate, setCloseDate] = useState(new Date().toISOString().split("T")[0]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chartCandles, setChartCandles] = useState<Candle[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  async function loadTrades() {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/trades/open`, { cache: "no-store" });
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();
      setOpenTrades(data);
      setActiveTrade(null);
      setActionMode(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setIsLoading(false);
    }
  }

  function handleActionClick(trade: Trade, mode: "UPDATE_STOP" | "CLOSE") {
    setActiveTrade(trade);
    setActionMode(mode);
    setNewStop(trade.stop_price ? trade.stop_price.toString() : "");
    setClosePrice(trade.current_close ? trade.current_close.toString() : "");
    // fetch chart data for this symbol
    setChartCandles([]);
    setChartLoading(true);
    fetch(`${apiBaseUrl}/ohlcv/${trade.symbol}?days=90`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setChartCandles(data.candles ?? []))
      .catch(() => setChartCandles([]))
      .finally(() => setChartLoading(false));
  }

  async function handleSubmitAction(e: React.FormEvent) {
    e.preventDefault();
    if (!activeTrade) return;
    setIsSubmitting(true);
    try {
      if (actionMode === "UPDATE_STOP") {
        const payload = { stop_price: Number(newStop) };
        const res = await fetch(`${apiBaseUrl}/trades/${activeTrade.id}/update-stop`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to update stop");
      } else if (actionMode === "CLOSE") {
        const payload = { exit_date: closeDate, exit_price: Number(closePrice) };
        const res = await fetch(`${apiBaseUrl}/trades/${activeTrade.id}/close`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Failed to close trade");
      }
      await loadTrades();
    } catch (err) {
      alert("Error: " + String(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  const trades = openTrades?.items ?? [];

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Trade Book</h1>
          <p>Active Positions Management</p>
        </div>
        <div className="topbarControls">
          <a href="/" style={{ display: "flex", alignItems: "center", gap: "6px", textDecoration: "none", color: "var(--text-main)", background: "var(--bg-card)", padding: "4px 8px", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
            <Home size={16} /> Dashboard
          </a>
          <button
            className="iconButton"
            disabled={isLoading}
            onClick={loadTrades}
            title="Reload trades"
            type="button"
          >
            <RefreshCw size={16} />
          </button>
          <div className={`statusPill ${!openTrades ? "offline" : "online"}`}>
             {!openTrades ? <><AlertTriangle size={16}/> API offline</> : <><CheckCircle2 size={16}/> API connected</>}
          </div>
        </div>
      </header>

      {error && (
        <div className="errorBanner">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      {activeTrade && actionMode && (
        <section className="panel" style={{ background: "var(--bg-card)" }}>
          <div className="panelHeader" style={{ borderBottom: "1px solid var(--border-subtle)", paddingBottom: "12px", marginBottom: "12px" }}>
            <h2>{actionMode === "UPDATE_STOP" ? "Update Stop Loss" : "Close Trade"}: {activeTrade.symbol}</h2>
          </div>
          <form onSubmit={handleSubmitAction} style={{ display: "flex", gap: "16px", alignItems: "flex-end" }}>
            {actionMode === "UPDATE_STOP" && (
              <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                <span className="label">New Stop Price</span>
                <input 
                  type="number" step="0.05" required value={newStop} onChange={e => setNewStop(e.target.value)}
                  style={{ background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", padding: "6px", borderRadius: "4px" }} 
                />
              </label>
            )}
            {actionMode === "CLOSE" && (
              <>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <span className="label">Exit Price</span>
                  <input 
                    type="number" step="0.05" required value={closePrice} onChange={e => setClosePrice(e.target.value)}
                    style={{ background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", padding: "6px", borderRadius: "4px" }} 
                  />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                  <span className="label">Exit Date</span>
                  <input 
                    type="date" required value={closeDate} onChange={e => setCloseDate(e.target.value)}
                    style={{ background: "var(--bg-base)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", padding: "6px", borderRadius: "4px", colorScheme: "dark" }} 
                  />
                </label>
              </>
            )}
            <div style={{ display: "flex", gap: "8px" }}>
              <button type="submit" disabled={isSubmitting} style={{ fontWeight: "bold", background: "var(--text-brand)", color: "#111", padding: "6px 12px", borderRadius: "4px", border: "none" }}>
                {isSubmitting ? "Submitting..." : "Confirm"}
              </button>
              <button type="button" onClick={() => setActiveTrade(null)} style={{ background: "var(--bg-base)", color: "var(--text-main)", padding: "6px 12px", borderRadius: "4px", border: "1px solid var(--border-subtle)" }}>
                Cancel
              </button>
            </div>
          </form>
          {chartLoading ? (
            <div style={{ fontSize: "11px", color: "var(--text-muted,#64748b)", paddingTop: "12px" }}>Loading chart…</div>
          ) : (
            <CandleChart
              candles={chartCandles}
              entryPrice={activeTrade.entry_price}
              stopPrice={actionMode === "UPDATE_STOP" ? (Number(newStop) || activeTrade.stop_price) : activeTrade.stop_price}
              height={260}
            />
          )}
        </section>
      )}

      <section className="panel wide">
        <div className="panelHeader">
          <span className="panelIcon"><Clock3 size={18} /></span>
          <h2>Open Positions Management</h2>
        </div>
        {trades.length === 0 ? (
          <div className="empty">No open trades.</div>
        ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Setup</th>
                  <th className="num">Entry</th>
                  <th className="num">Stop</th>
                  <th className="num">Close</th>
                  <th className="num">P&L</th>
                  <th className="num">Gain</th>
                  <th>Action</th>
                  <th>Manage</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => {
                  const isActive = activeTrade?.id === trade.id;
                  return (
                    <tr key={trade.id} className={isActive ? "selectedRow" : ""}>
                      <td><strong>{trade.symbol}</strong></td>
                      <td>{trade.setup_type.replaceAll("_", " ")}</td>
                      <td className="num">{formatCurrency(trade.entry_price)}</td>
                      <td className="num">{formatCurrency(trade.stop_price)}</td>
                      <td className="num">{formatCurrency(trade.current_close)}</td>
                      <td className="num" style={{ color: (trade.unrealized_pnl ?? 0) >= 0 ? "var(--text-good)" : "var(--text-bad)" }}>
                        {formatCurrency(trade.unrealized_pnl)}
                      </td>
                      <td className="num" style={{ color: (trade.pct_gain ?? 0) >= 0 ? "var(--text-good)" : "var(--text-bad)" }}>
                        {formatNumber(trade.pct_gain, 2)}%
                      </td>
                      <td>
                        <span style={{ color: trade.action_required !== "NONE" ? "var(--text-warn)" : "inherit" }}>
                          {trade.action_required.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: "flex", gap: "6px" }}>
                          <button onClick={() => handleActionClick(trade, "UPDATE_STOP")} style={{ background: "var(--bg-base)", border: "1px solid var(--border-subtle)", padding: "2px 6px", borderRadius: "4px", fontSize: "12px", color: "var(--text-main)" }}>Modify Stop</button>
                          <button onClick={() => handleActionClick(trade, "CLOSE")} style={{ background: "var(--bg-base)", border: "1px solid var(--border-subtle)", padding: "2px 6px", borderRadius: "4px", fontSize: "12px", color: "var(--text-main)" }}>Close</button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer>
        <TrendingUp size={16} />
        <span>Live Management View backed by {apiBaseUrl}</span>
      </footer>
    </main>
  );
}
