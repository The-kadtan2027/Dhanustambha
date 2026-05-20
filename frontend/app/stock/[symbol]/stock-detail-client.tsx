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

  const openTrade = initialTradeData?.trades?.find((t) => t.status === "OPEN") ?? null;
  const closedTrades = initialTradeData?.trades?.filter((t) => t.status !== "OPEN") ?? [];
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
