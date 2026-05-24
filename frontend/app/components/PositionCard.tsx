"use client";

import { useState, useEffect } from "react";
import type { Trade } from "../../types/api";
import { formatCurrency, formatNumber, labelFromToken } from "../../lib/format";
import CandleChart, { type Candle } from "./CandleChart";

type Props = {
  trade: Trade;
  apiBaseUrl: string;
  onManageClick: (trade: Trade, mode: "UPDATE_STOP" | "CLOSE") => void;
};

export default function PositionCard({ trade, apiBaseUrl, onManageClick }: Props) {
  const [candles, setCandles] = useState<Candle[]>([]);

  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    fetch(`${apiBaseUrl}/ohlcv/${trade.symbol}?days=90`)
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((d) => {
        const fetched: Candle[] = d.candles ?? [];
        // Append a synthetic live candle for today if the DB data is stale
        // and we have a live CMP on the trade object.
        if (
          trade.current_close != null &&
          fetched.length > 0 &&
          fetched[fetched.length - 1].time !== today
        ) {
          const prev = fetched[fetched.length - 1];
          fetched.push({
            time: today,
            open: prev.close,
            high: Math.max(prev.close, trade.current_close),
            low: Math.min(prev.close, trade.current_close),
            close: trade.current_close,
            volume: 0,
            ma20: null,
            ma50: null,
          });
        }
        setCandles(fetched);
      })
      .catch(() => setCandles([]));
  }, [trade.symbol, apiBaseUrl]);

  const gain = trade.pct_gain ?? 0;
  const stopLossHit = trade.action_required === "STOP_LOSS_HIT";
  const cardClass = stopLossHit ? "stopHit" : gain > 0 ? "winner" : gain < 0 ? "loser" : "flat";
  const gainColor = gain >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div className={`positionCard ${cardClass}`}>
      <div className="positionCardHeader">
        <div>
          <div className="positionCardSymbol">{trade.symbol}</div>
          <div className="positionCardMeta">
            {labelFromToken(trade.setup_type)} · {trade.days_held ?? 0}d held
            {trade.action_required !== "NONE" && (
              <span
                style={{
                  color: stopLossHit ? "var(--red)" : "var(--amber)",
                  marginLeft: 8,
                  fontWeight: 700,
                }}
              >
                ⚠ {labelFromToken(trade.action_required)}
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
          setupType={trade.setup_type}
          signalDate={trade.entry_date ?? undefined}
          height={240}
        />
      </div>

      <div className="positionCardFooter">
        <span>{trade.shares ?? "-"} shares</span>
        <div style={{ display: "flex", gap: 8 }}>
          {!stopLossHit && (
            <button
              onClick={() => onManageClick(trade, "UPDATE_STOP")}
              style={{ background: "var(--panel)", border: "1px solid var(--line)", padding: "3px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12 }}
            >
              Modify Stop
            </button>
          )}
          <button
            onClick={() => onManageClick(trade, "CLOSE")}
            style={{
              background: stopLossHit ? "var(--red)" : "var(--text)",
              color: "white",
              border: "none",
              padding: "3px 10px",
              borderRadius: 4,
              cursor: "pointer",
              fontSize: 12,
              fontWeight: stopLossHit ? 700 : 400,
            }}
          >
            {stopLossHit ? "Close Now" : "Close"}
          </button>
        </div>
      </div>
    </div>
  );
}
