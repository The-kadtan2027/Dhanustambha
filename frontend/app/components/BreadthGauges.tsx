"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
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

const REGIME_COLOR: Record<string, string> = {
  OFFENSIVE: "#22c55e",
  DEFENSIVE: "#f59e0b",
  AVOID: "#ef4444",
};

function regimeLabel(market: Market): { text: string; cls: string } {
  const ma20 = market.pct_above_ma20 ?? 0;
  if (market.verdict === "OFFENSIVE" && ma20 >= 65) return { text: "Strongly Bullish", cls: "bullish" };
  if (market.verdict === "OFFENSIVE") return { text: "Moderately Bullish", cls: "bullish" };
  if (market.verdict === "DEFENSIVE") return { text: "Cautious", cls: "cautious" };
  if (market.verdict === "AVOID" && ma20 < 35) return { text: "Bearish", cls: "bearish" };
  return { text: "Cautious / Avoid", cls: "cautious" };
}

function findRegimeChangesDates(history: Market[]): Array<{ date: string; verdict: string }> {
  const changes: Array<{ date: string; verdict: string }> = [];
  for (let index = 1; index < history.length; index += 1) {
    const previous = history[index - 1].verdict;
    const current = history[index].verdict;
    if (previous && current && previous !== current) {
      changes.push({ date: history[index].date?.slice(5) ?? "", verdict: current });
    }
  }
  return changes;
}

function SparkCard({
  title,
  value,
  unit,
  data,
  dataKey,
  color,
  regimeChanges,
}: {
  title: string;
  value: number | null;
  unit?: string;
  data: Record<string, unknown>[];
  dataKey: string;
  color: string;
  regimeChanges: Array<{ date: string; verdict: string }>;
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
          <XAxis dataKey="date" hide />
          <YAxis hide />
          {(dataKey === "ma20" || dataKey === "ma50" || dataKey === "netHL") && (
            <ReferenceLine
              y={dataKey === "ma20" ? 55 : dataKey === "ma50" ? 50 : 0}
              stroke="rgba(23, 32, 42, 0.25)"
              strokeDasharray="4 4"
            />
          )}
          <Area
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#grad-${dataKey})`}
            dot={false}
          />
          {regimeChanges.map((regimeChange) => (
            <ReferenceLine
              key={`${regimeChange.date}-${regimeChange.verdict}`}
              x={regimeChange.date}
              stroke={REGIME_COLOR[regimeChange.verdict] ?? "#94a3b8"}
              strokeWidth={1}
              strokeDasharray="3 3"
            />
          ))}
          <Tooltip
            contentStyle={{
              background: "#1e293b",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: 6,
              fontSize: 11,
              padding: "4px 8px",
            }}
            itemStyle={{ color: "#fff" }}
            labelStyle={{ color: "#94a3b8", marginBottom: 2 }}
            labelFormatter={(label) => `Date: ${label}`}
            formatter={((val: unknown) => [
              val != null ? `${Number(val).toFixed(1)}${unit ?? ""}` : "-",
              title,
            ]) as never}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function BreadthGauges({ market, history: initialHistory, apiBaseUrl }: Props) {
  const [days, setDays] = useState(90);
  const [history, setHistory] = useState<Market[]>(initialHistory);
  const [chartHeight, setChartHeight] = useState(100);

  useEffect(() => {
    fetch(`${apiBaseUrl}/market/breadth/history?days=${days}`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload) => setHistory(payload.items ?? []))
      .catch(() => {});
  }, [apiBaseUrl, days]);

  const regime = regimeLabel(market);
  const advancing = market.advancing ?? 0;
  const declining = market.declining ?? 0;
  const total = advancing + declining || 1;
  const advPct = (advancing / total) * 100;
  const ratio = declining > 0 ? (advancing / declining).toFixed(2) : "inf";

  const chartData = history.map((row) => ({
    date: row.date?.slice(5) ?? "",
    ma20: row.pct_above_ma20 ?? null,
    ma50: row.pct_above_ma50 ?? null,
    netHL: (row.new_highs_52w ?? 0) - (row.new_lows_52w ?? 0),
    netAD: (row.advancing ?? 0) - (row.declining ?? 0),
  }));

  const regimeChanges = findRegimeChangesDates(history);

  return (
    <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span className={`regimeBadge ${regime.cls}`}>Diamond {regime.text}</span>
        <div className="chartToolbar">
          <div className="timeframeBar">
            {TIMEFRAMES.map((timeframe) => (
              <button
                key={timeframe.label}
                className={`timeframeBtn ${days === timeframe.days ? "active" : ""}`}
                onClick={() => setDays(timeframe.days)}
                type="button"
              >
                {timeframe.label}
              </button>
            ))}
          </div>
          <div className="chartResizeControls">
            <button
              type="button"
              className="timeframeBtn"
              aria-label="Compact Breadth Charts"
              onClick={() => setChartHeight((value) => Math.max(80, value - 20))}
            >
              Compact Breadth Charts
            </button>
            <button
              type="button"
              className="timeframeBtn"
              aria-label="Expand Breadth Charts"
              onClick={() => setChartHeight((value) => Math.min(180, value + 20))}
            >
              Expand Breadth Charts
            </button>
          </div>
        </div>
      </div>

      {regimeChanges.length > 0 && (
        <div style={{ display: "flex", gap: 12, fontSize: 10, color: "#64748b", flexWrap: "wrap" }}>
          <span>Regime shifts:</span>
          {Object.entries(REGIME_COLOR).map(([verdict, color]) => (
            <span key={verdict} style={{ display: "flex", alignItems: "center", gap: 3 }}>
              <span style={{ display: "inline-block", width: 12, borderTop: `2px dashed ${color}` }} />
              {verdict}
            </span>
          ))}
        </div>
      )}

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

      <div>
        <div className="label" style={{ marginBottom: 6 }}>Daily Advances - Declines</div>
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
            <XAxis dataKey="date" hide />
            <YAxis hide />
            <ReferenceLine y={0} stroke="rgba(23, 32, 42, 0.25)" />
            <Tooltip
              contentStyle={{
                background: "#1e293b",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: 6,
                fontSize: 11,
                padding: "4px 8px",
              }}
              itemStyle={{ color: "#fff" }}
              labelStyle={{ color: "#94a3b8" }}
              labelFormatter={(label) => `Date: ${label}`}
              formatter={((val: unknown) => [
                val != null ? Number(val).toLocaleString() : "-",
                "Net A/D",
              ]) as never}
            />
            <Bar dataKey="netAD" name="Net A/D" fill="#22c55e" isAnimationActive={false} />
            {regimeChanges.map((regimeChange) => (
              <ReferenceLine
                key={`ad-${regimeChange.date}`}
                x={regimeChange.date}
                stroke={REGIME_COLOR[regimeChange.verdict] ?? "#94a3b8"}
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="breadthSparkGrid">
        <SparkCard
          title="% Above MA20"
          value={market.pct_above_ma20}
          unit="%"
          data={chartData}
          dataKey="ma20"
          color={(market.pct_above_ma20 ?? 0) >= 55 ? "#22c55e" : (market.pct_above_ma20 ?? 0) >= 45 ? "#f59e0b" : "#ef4444"}
          regimeChanges={regimeChanges}
        />
        <SparkCard
          title="% Above MA50"
          value={market.pct_above_ma50}
          unit="%"
          data={chartData}
          dataKey="ma50"
          color={(market.pct_above_ma50 ?? 0) >= 50 ? "#22c55e" : "#ef4444"}
          regimeChanges={regimeChanges}
        />
        <SparkCard
          title="Net Highs/Lows"
          value={(market.new_highs_52w ?? 0) - (market.new_lows_52w ?? 0)}
          data={chartData}
          dataKey="netHL"
          color={((market.new_highs_52w ?? 0) - (market.new_lows_52w ?? 0)) >= 0 ? "#22c55e" : "#ef4444"}
          regimeChanges={regimeChanges}
        />
      </div>
    </div>
  );
}
