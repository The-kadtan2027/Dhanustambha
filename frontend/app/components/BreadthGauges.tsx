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
