"use client";

import { useState, useEffect } from "react";
import type { Trade } from "../../types/api";
import { formatCurrency, formatNumber } from "../../lib/format";
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
