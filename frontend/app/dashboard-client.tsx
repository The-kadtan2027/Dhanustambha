"use client";

import { useMemo, useState, useEffect } from "react";
import Link from "next/link";
import BreadthGauges from "./components/BreadthGauges";
import LiveScanController from "./components/LiveScanController";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Filter,
  RefreshCw,
  ShieldAlert,
  TrendingUp
} from "lucide-react";

import type { Market, Briefing, DateList, Trade, TradeList, TradeSummary } from '../types/api';
import { formatNumber, labelFromToken, verdictClass } from '../lib/format';
import { fetchJson } from '../lib/api';

import Card from './components/ui/Card';
import EmptyState from './components/ui/EmptyState';
import Metric from './components/ui/Metric';
import SummaryPanel from './components/ui/SummaryPanel';

export type DashboardClientProps = {
  apiBaseUrl: string;
  initialBriefing: Briefing | null;
  initialDates: DateList | null;
  initialActions: TradeList | null;
  initialSummary: TradeSummary | null;
};

function MarketPanel({ market, apiBaseUrl }: { market: Market | null; apiBaseUrl: string }) {
  const [breadthHistory, setBreadthHistory] = useState<Market[]>([]);

  useEffect(() => {
    if (!market) return;
    fetch(`${apiBaseUrl}/market/breadth/history?days=60`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setBreadthHistory(data.items ?? []))
      .catch(() => setBreadthHistory([]));
  }, [market, apiBaseUrl]);

  if (!market) {
    return (
      <Card title="Market Monitor" icon={<Activity size={18} />}>
        <EmptyState text="No stored breadth reading is available." />
      </Card>
    );
  }

  return (
    <Card title="Market Monitor" icon={<Activity size={18} />}>
      <div className="marketTopline">
        <div>
          <span className="label">Verdict</span>
          <strong className={`verdict ${verdictClass(market.verdict)}`}>
            {market.verdict}
          </strong>
        </div>
        <div className="marketPanelActions">
          <span className="datePill">{market.date}</span>
          <Link className="textButton" href="/market">
            <BarChart3 size={14} /> Full monitor
          </Link>
        </div>
      </div>
      <div className="metricGrid">
        <Metric label="Above MA20" value={`${formatNumber(market.pct_above_ma20)}%`} />
        <Metric label="Above MA50" value={`${formatNumber(market.pct_above_ma50)}%`} />
        <Metric label="52w Highs" value={formatNumber(market.new_highs_52w, 0)} />
        <Metric label="52w Lows" value={formatNumber(market.new_lows_52w, 0)} />
        <Metric label="Up Volume" value={formatNumber(market.up_volume_ratio, 2)} />
        <Metric
          label="Adv / Dec"
          value={`${formatNumber(market.advancing, 0)} / ${formatNumber(market.declining, 0)}`}
        />
      </div>
      <BreadthGauges market={market} history={breadthHistory} apiBaseUrl={apiBaseUrl} />
    </Card>
  );
}

function TradeActionsPanel({
  trades,
  filter,
  onFilterChange
}: {
  trades: Trade[];
  filter: string;
  onFilterChange: (filter: string) => void;
}) {
  const actionTypes = [
    "ALL",
    "STOP_LOSS_HIT",
    "TRAIL_TO_BREAKEVEN",
    "TRAIL_TO_3PCT",
    "TRAIL_TO_7_5PCT",
    "TIME_EXIT"
  ];
  const filteredTrades =
    filter === "ALL" ? trades : trades.filter((trade) => trade.action_required === filter);

  return (
    <Card title="Required Actions" icon={<ShieldAlert size={18} />}>
      <div className="segmented" aria-label="Trade action filters">
        {actionTypes.map((actionType) => (
          <button
            className={filter === actionType ? "active" : ""}
            key={actionType}
            onClick={() => onFilterChange(actionType)}
            type="button"
          >
            {labelFromToken(actionType)}
          </button>
        ))}
      </div>
      {filteredTrades.length === 0 ? (
        <EmptyState text="No open trade matches this action filter." />
      ) : (
        <div className="actionList">
          {filteredTrades.map((trade) => (
            <div className="actionItem" key={trade.id}>
              <div>
                <strong>{trade.symbol}</strong>
                <span>{labelFromToken(trade.action_required)}</span>
              </div>
              <div className="actionMeta">
                {formatNumber(trade.pct_gain, 2)}% / {trade.days_held ?? "-"}d
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export default function DashboardClient({
  apiBaseUrl,
  initialActions,
  initialBriefing,
  initialDates,
  initialSummary
}: DashboardClientProps) {
  const [briefing, setBriefing] = useState(initialBriefing);
  const [dates, setDates] = useState(initialDates?.items ?? []);
  const [actions, setActions] = useState(initialActions);
  const [summary, setSummary] = useState(initialSummary);
  const [selectedDate, setSelectedDate] = useState(initialBriefing?.date ?? "");
  const [actionFilter, setActionFilter] = useState("ALL");
  const [isLoading, setIsLoading] = useState(false);
  const [isRunningBriefing, setIsRunningBriefing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRunBriefing() {
    setIsRunningBriefing(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/briefing/run`, {
        method: "POST"
      });
      if (!res.ok) {
        const payload = await res.json().catch(() => null);
        throw new Error(payload?.detail ?? `Briefing run failed: ${res.status}`);
      }
      
      // on success, fetch the latest standard dashboard data again
      await loadDashboard("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run briefing failed");
    } finally {
      setIsRunningBriefing(false);
    }
  }

  const apiUnavailable = !briefing && !actions && !summary;
  const knownDates = useMemo(() => {
    if (selectedDate && !dates.includes(selectedDate)) {
      return [selectedDate, ...dates];
    }
    return dates;
  }, [dates, selectedDate]);

  async function loadDashboard(nextDate: string) {
    setIsLoading(true);
    setError(null);
    try {
      const briefingPath = nextDate ? `/briefing/${nextDate}` : "/briefing/latest";
      const [nextBriefing, nextDates, nextActions, nextSummary] =
        await Promise.all([
          fetchJson<Briefing>(apiBaseUrl, briefingPath),
          fetchJson<DateList>(apiBaseUrl, "/briefing/dates"),
          fetchJson<TradeList>(apiBaseUrl, "/trades/actions"),
          fetchJson<TradeSummary>(apiBaseUrl, "/trades/summary")
        ]);

      setBriefing(nextBriefing);
      setDates(nextDates.items);
      setActions(nextActions);
      setSummary(nextSummary);
      setSelectedDate(nextBriefing.date);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Request failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <div className="topbarControls" style={{ marginBottom: "16px" }}>
        <button
          onClick={handleRunBriefing}
          disabled={isRunningBriefing}
          style={{ background: "#4caf50", color: "#fff", border: "none", padding: "4px 12px", borderRadius: "4px", fontWeight: "bold", cursor: isRunningBriefing ? "not-allowed" : "pointer", fontSize: "13px" }}
        >
          {isRunningBriefing ? "Running EOD Briefing..." : "Run EOD Briefing ⚡"}
        </button>
        <span style={{ borderLeft: "1px solid var(--border-subtle)", margin: "0 8px", height: "24px" }} />
        <LiveScanController apiBaseUrl={apiBaseUrl} onComplete={() => loadDashboard("")} label="Live Briefing 🚀" />
        <span style={{ borderLeft: "1px solid var(--border-subtle)", margin: "0 8px", height: "24px" }} />
        <label className="dateControl">
          <span className="label">Briefing date</span>
          <select
            disabled={knownDates.length === 0 || isLoading}
            onChange={(event) => loadDashboard(event.target.value)}
            value={selectedDate}
          >
            {knownDates.length === 0 ? (
              <option value="">No dates</option>
            ) : (
              knownDates.map((date) => (
                <option key={date} value={date}>
                  {date}
                </option>
              ))
            )}
          </select>
        </label>
        <button
          className="iconButton"
          disabled={isLoading}
          onClick={() => loadDashboard(selectedDate)}
          title="Refresh data"
          type="button"
        >
          <RefreshCw size={16} />
        </button>
        <div className={`statusPill ${apiUnavailable ? "offline" : "online"}`}>
          {apiUnavailable ? (
            <><AlertTriangle size={16} /> API offline</>
          ) : (
            <><CheckCircle2 size={16} /> API connected</>
          )}
        </div>
      </div>

      {error && (
        <div className="errorBanner">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button onClick={() => loadDashboard(selectedDate)} type="button">
            Retry
          </button>
        </div>
      )}

      <div className="heroBand">
        <div>
          <span className="label">Selected briefing</span>
          <strong>{briefing?.date ?? "-"}</strong>
        </div>
        <div>
          <span className="label">Actions</span>
          <strong>{actions?.count ?? 0}</strong>
        </div>
      </div>

      <section className="grid">
        <MarketPanel market={briefing?.market ?? null} apiBaseUrl={apiBaseUrl} />
        <TradeActionsPanel
          filter={actionFilter}
          onFilterChange={setActionFilter}
          trades={actions?.items ?? []}
        />
        <SummaryPanel summary={summary} />
      </section>

      <footer>
        <TrendingUp size={16} />
        <span>Read-only view backed by {apiBaseUrl}</span>
        <span className="footerFilter">
          <Filter size={14} /> {labelFromToken(actionFilter)}
        </span>
      </footer>
    </main>
  );
}
