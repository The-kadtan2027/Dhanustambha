"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, RefreshCw, CheckCircle2, LayoutGrid, List } from "lucide-react";
import type { Trade, TradeList, PortfolioSummary } from "../../types/api";
import { formatCurrency, labelFromToken } from "../../lib/format";
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

  async function loadTrades(isLive: boolean = false) {
    if (!isLive) setIsLoading(true);
    setError(null);
    try {
      const qs = isLive ? "?live=true" : "";
      const [t, p] = await Promise.all([
        fetch(`${apiBaseUrl}/trades/open${qs}`, { cache: "no-store" }).then((r) => r.json()),
        fetch(`${apiBaseUrl}/trades/portfolio${qs}`, { cache: "no-store" }).then((r) => r.json()),
      ]);
      setOpenTrades(t);
      setPortfolio(p);
      if (!isLive) {
        setActiveTrade(null);
        setActionMode(null);
      }
    } catch (e) { 
      if (!isLive) setError(String(e)); 
    } finally { 
      if (!isLive) setIsLoading(false); 
    }
  }

  // Stream H: Live Polling
  useEffect(() => {
    const timer = setInterval(() => loadTrades(true), 60000); // 60s live refresh
    return () => clearInterval(timer);
  }, [apiBaseUrl]);

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
          <button className="iconButton" disabled={isLoading} onClick={() => loadTrades()} title="Refresh">
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
                    <td>{labelFromToken(t.setup_type)}</td>
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
                      {labelFromToken(t.action_required)}
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
