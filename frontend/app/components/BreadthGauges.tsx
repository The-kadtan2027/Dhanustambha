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
