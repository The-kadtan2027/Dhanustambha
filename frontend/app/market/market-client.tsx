"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  RefreshCw,
  TrendingUp
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import type { Market } from "../../types/api";
import { formatNumber, verdictClass } from "../../lib/format";

type Props = {
  apiBaseUrl: string;
  initialMarket: Market | null;
  initialHistory: Market[];
};

const TIMEFRAMES = [
  { label: "1M", days: 30 },
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 }
];

function regimeLabel(market: Market | null): { text: string; cls: string } {
  if (!market) {
    return { text: "No Breadth Data", cls: "cautious" };
  }
  const verdict = market.verdict.toUpperCase();
  const ma20 = market.pct_above_ma20 ?? 0;
  if (verdict === "OFFENSIVE" && ma20 >= 65) {
    return { text: "Strongly Bullish", cls: "bullish" };
  }
  if (verdict === "OFFENSIVE") {
    return { text: "Moderately Bullish", cls: "bullish" };
  }
  if (verdict === "DEFENSIVE") {
    return { text: "Cautious", cls: "cautious" };
  }
  if (verdict === "AVOID" && ma20 < 35) {
    return { text: "Bearish", cls: "bearish" };
  }
  return { text: "Cautious / Avoid", cls: "cautious" };
}

function metricDelta(current: number | null | undefined, previous: number | null | undefined): string {
  if (current == null || previous == null) {
    return "-";
  }
  const delta = current - previous;
  return `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
}

function BreadthMetric({
  label,
  value,
  helper,
  tone = "neutral"
}: {
  label: string;
  value: string;
  helper: string;
  tone?: "good" | "warn" | "bad" | "neutral";
}) {
  return (
    <div className={`marketMetric ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{helper}</small>
    </div>
  );
}

function SparkPanel({
  title,
  value,
  data,
  dataKey,
  color,
  unit = ""
}: {
  title: string;
  value: number | null | undefined;
  data: Record<string, unknown>[];
  dataKey: string;
  color: string;
  unit?: string;
}) {
  return (
    <section className="marketChartPanel">
      <div className="marketChartHeader">
        <span>{title}</span>
        <strong style={{ color }}>{value == null ? "-" : `${value.toFixed(1)}${unit}`}</strong>
      </div>
      <ResponsiveContainer width="100%" height={190}>
        <AreaChart data={data} margin={{ top: 12, right: 8, left: -24, bottom: 0 }}>
          <defs>
            <linearGradient id={`market-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={color} stopOpacity={0.32} />
              <stop offset="95%" stopColor={color} stopOpacity={0.04} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted)" }} />
          <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} />
          <Tooltip
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--line)",
              borderRadius: 6,
              fontSize: 12
            }}
          />
          <Area
            dataKey={dataKey}
            dot={false}
            fill={`url(#market-${dataKey})`}
            stroke={color}
            strokeWidth={2}
            type="monotone"
          />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  );
}

export default function MarketClient({ apiBaseUrl, initialMarket, initialHistory }: Props) {
  const [market, setMarket] = useState(initialMarket);
  const [history, setHistory] = useState(initialHistory);
  const [days, setDays] = useState(90);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadMarket(nextDays = days) {
    setIsLoading(true);
    setError(null);
    try {
      const [latestResponse, historyResponse] = await Promise.all([
        fetch(`${apiBaseUrl}/market/breadth/latest`, { cache: "no-store" }),
        fetch(`${apiBaseUrl}/market/breadth/history?days=${nextDays}`, { cache: "no-store" })
      ]);
      if (!latestResponse.ok || !historyResponse.ok) {
        throw new Error("Market breadth API is unavailable.");
      }
      const latest = (await latestResponse.json()) as Market;
      const nextHistory = (await historyResponse.json()) as { items: Market[] };
      setMarket(latest);
      setHistory(nextHistory.items ?? []);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to load market breadth.");
    } finally {
      setIsLoading(false);
    }
  }

  function selectTimeframe(nextDays: number) {
    setDays(nextDays);
    void loadMarket(nextDays);
  }

  const chartData = useMemo(
    () =>
      history.map((row) => ({
        date: row.date?.slice(5) ?? "",
        ma20: row.pct_above_ma20 ?? null,
        ma50: row.pct_above_ma50 ?? null,
        upVolume: row.up_volume_ratio == null ? null : row.up_volume_ratio * 100,
        netAD: (row.advancing ?? 0) - (row.declining ?? 0),
        netHL: (row.new_highs_52w ?? 0) - (row.new_lows_52w ?? 0)
      })),
    [history]
  );
  const previous = history.length > 1 ? history[history.length - 2] : null;
  const regime = regimeLabel(market);
  const advancing = market?.advancing ?? 0;
  const declining = market?.declining ?? 0;
  const totalAD = advancing + declining || 1;
  const advPct = (advancing / totalAD) * 100;
  const ratio = declining > 0 ? advancing / declining : null;
  const netHL = (market?.new_highs_52w ?? 0) - (market?.new_lows_52w ?? 0);

  return (
    <main className="shell marketShell">
      <header className="marketHeader">
        <div>
          <span className="label">Market breadth</span>
          <h1>Market Monitor</h1>
          <p>
            Breadth decides sizing posture before any scanner candidate deserves attention.
          </p>
        </div>
        <div className="marketHeaderActions">
          <div className="timeframeBar" aria-label="Market breadth timeframe">
            {TIMEFRAMES.map((timeframe) => (
              <button
                className={`timeframeBtn ${days === timeframe.days ? "active" : ""}`}
                disabled={isLoading}
                key={timeframe.label}
                onClick={() => selectTimeframe(timeframe.days)}
                type="button"
              >
                {timeframe.label}
              </button>
            ))}
          </div>
          <button
            className="iconButton"
            disabled={isLoading}
            onClick={() => loadMarket()}
            title="Refresh market breadth"
            type="button"
          >
            <RefreshCw size={16} />
          </button>
        </div>
      </header>

      {error && (
        <div className="errorBanner">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}

      <section className="marketRegimeBand">
        <div>
          <span className={`regimeBadge ${regime.cls}`}>
            {regime.text}
          </span>
          <strong className={`verdict ${verdictClass(market?.verdict)}`}>
            {market?.verdict ?? "-"}
          </strong>
        </div>
        <div>
          <span className="label">Latest reading</span>
          <strong>{market?.date ?? "-"}</strong>
        </div>
        <div>
          <span className="label">A/D ratio</span>
          <strong>{ratio == null ? "-" : `${ratio.toFixed(2)} : 1`}</strong>
        </div>
        <div>
          <span className="label">Net highs/lows</span>
          <strong className={netHL >= 0 ? "positiveText" : "negativeText"}>
            {netHL >= 0 ? "+" : ""}{netHL}
          </strong>
        </div>
      </section>

      <section className="marketMetricStrip">
        <BreadthMetric
          helper={`Change ${metricDelta(market?.pct_above_ma20, previous?.pct_above_ma20)}`}
          label="Above MA20"
          tone={(market?.pct_above_ma20 ?? 0) >= 55 ? "good" : (market?.pct_above_ma20 ?? 0) >= 45 ? "warn" : "bad"}
          value={`${formatNumber(market?.pct_above_ma20)}%`}
        />
        <BreadthMetric
          helper={`Change ${metricDelta(market?.pct_above_ma50, previous?.pct_above_ma50)}`}
          label="Above MA50"
          tone={(market?.pct_above_ma50 ?? 0) >= 50 ? "good" : "bad"}
          value={`${formatNumber(market?.pct_above_ma50)}%`}
        />
        <BreadthMetric
          helper={`${formatNumber(market?.up_volume_ratio, 2)} ratio`}
          label="Up Volume"
          tone={(market?.up_volume_ratio ?? 0) >= 0.6 ? "good" : "warn"}
          value={`${formatNumber((market?.up_volume_ratio ?? 0) * 100)}%`}
        />
        <BreadthMetric
          helper={`${formatNumber(market?.new_highs_52w, 0)} highs / ${formatNumber(market?.new_lows_52w, 0)} lows`}
          label="52w Net H/L"
          tone={netHL >= 0 ? "good" : "bad"}
          value={`${netHL >= 0 ? "+" : ""}${netHL}`}
        />
      </section>

      <section className="marketDashboardGrid">
        <div className="marketChartPanel marketAdvancePanel">
          <div className="marketChartHeader">
            <span>Today's Advance / Decline</span>
            <strong>{ratio == null ? "-" : `${ratio.toFixed(2)} : 1`}</strong>
          </div>
          <div className="marketAdCounts">
            <div>
              <strong className="adCount adv">{advancing.toLocaleString()}</strong>
              <span>Advancing</span>
            </div>
            <div>
              <strong className="adCount dec">{declining.toLocaleString()}</strong>
              <span>Declining</span>
            </div>
          </div>
          <div className="adBar large">
            <div className="adv" style={{ width: `${advPct}%` }} />
            <div className="dec" style={{ width: `${100 - advPct}%` }} />
          </div>
        </div>

        <div className="marketChartPanel marketAdHistoryPanel">
          <div className="marketChartHeader">
            <span>Daily Advances - Declines</span>
            <strong>{days}d</strong>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} margin={{ top: 12, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} />
              <Tooltip
                contentStyle={{
                  background: "var(--panel)",
                  border: "1px solid var(--line)",
                  borderRadius: 6,
                  fontSize: 12
                }}
              />
              <Bar dataKey="netAD" isAnimationActive={false} name="Net A/D">
                {chartData.map((row) => (
                  <Cell
                    fill={(row.netAD as number) >= 0 ? "var(--green)" : "var(--red)"}
                    key={`${row.date}-${row.netAD}`}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="marketTrendGrid">
        <SparkPanel
          color="#2296c8"
          data={chartData}
          dataKey="ma20"
          title="% Above 20 MA"
          unit="%"
          value={market?.pct_above_ma20}
        />
        <SparkPanel
          color="#7c3aed"
          data={chartData}
          dataKey="ma50"
          title="% Above 50 MA"
          unit="%"
          value={market?.pct_above_ma50}
        />
        <SparkPanel
          color={netHL >= 0 ? "var(--green)" : "var(--red)"}
          data={chartData}
          dataKey="netHL"
          title="Net Highs / Lows"
          value={netHL}
        />
      </section>

      {history.length === 0 && (
        <section className="empty">
          No stored market breadth history is available yet. Start the API and run a briefing to
          populate this page.
        </section>
      )}

      <footer>
        <Activity size={16} />
        <span>Backed by {apiBaseUrl}</span>
        <span className="footerFilter">
          <BarChart3 size={14} /> {history.length} readings
        </span>
        <span className="footerFilter">
          <TrendingUp size={14} /> EOD breadth
        </span>
      </footer>
    </main>
  );
}
