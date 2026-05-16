"use client";

import { useMemo, useState, useEffect } from "react";
import CandleChart, { type Candle } from "./components/CandleChart";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Filter,
  RefreshCw,
  ShieldAlert,
  Target,
  TrendingUp
} from "lucide-react";

export type Market = {
  date: string;
  pct_above_ma20: number | null;
  pct_above_ma50: number | null;
  new_highs_52w: number | null;
  new_lows_52w: number | null;
  up_volume_ratio: number | null;
  advancing: number | null;
  declining: number | null;
  verdict: string;
};

export type WatchlistItem = {
  symbol: string;
  setup_type: string;
  score: number | null;
  pct_change: number | null;
  volume_ratio: number | null;
  close: number | null;
  notes: string | null;
};

export type Briefing = {
  date: string;
  market: Market;
  watchlist: WatchlistItem[];
  watchlist_count: number;
};

export type DateList = {
  count: number;
  items: string[];
};

export type Trade = {
  id: number;
  symbol: string;
  setup_type: string;
  entry_date: string;
  entry_price: number | null;
  shares: number | null;
  stop_price: number | null;
  current_close: number | null;
  unrealized_pnl: number | null;
  pct_gain: number | null;
  days_held: number | null;
  action_required: string;
};

export type TradeList = {
  count: number;
  items: Trade[];
};

export type TradeSummary = {
  total_trades: number;
  win_rate: number;
  avg_win_r: number;
  avg_loss_r: number;
  expectancy_r: number;
};

type DashboardClientProps = {
  apiBaseUrl: string;
  initialBriefing: Briefing | null;
  initialDates: DateList | null;
  initialOpenTrades: TradeList | null;
  initialActions: TradeList | null;
  initialSummary: TradeSummary | null;
};

async function fetchJson<T>(apiBaseUrl: string, path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

function formatNumber(value: number | null, digits = 1): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

function formatCurrency(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 2,
    minimumFractionDigits: 2
  }).format(value);
}

function verdictClass(verdict: string): string {
  const normalized = verdict.toUpperCase();
  if (normalized === "OFFENSIVE") {
    return "good";
  }
  if (normalized === "DEFENSIVE") {
    return "warn";
  }
  return "bad";
}

function setupLabel(setupType: string, notes: string | null): string {
  const marker = notes?.includes("A+") ? "A+ " : notes?.includes("HIGH") ? "HIGH " : "";
  return `${marker}${setupType.replaceAll("_", " ")}`;
}

function Card({
  title,
  icon,
  children,
  className = ""
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panelHeader">
        <span className="panelIcon">{icon}</span>
        <h2>{title}</h2>
      </div>
      {children}
    </section>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty">{text}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MarketPanel({ market }: { market: Market | null }) {
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
        <span className="datePill">{market.date}</span>
      </div>
      <div className="metricGrid">
        <Metric label="Above MA20" value={`${formatNumber(market.pct_above_ma20)}%`} />
        <Metric label="Above MA50" value={`${formatNumber(market.pct_above_ma50)}%`} />
        <Metric label="52w Highs" value={formatNumber(market.new_highs_52w, 0)} />
        <Metric label="52w Lows" value={formatNumber(market.new_lows_52w, 0)} />
        <Metric label="Up Volume" value={formatNumber(market.up_volume_ratio, 2)} />
        <Metric
          label="Adv / Dec"
          value={`${formatNumber(market.advancing, 0)} / ${formatNumber(
            market.declining,
            0
          )}`}
        />
      </div>
    </Card>
  );
}

function WatchlistPanel({
  items,
  selectedItem,
  onSelect
}: {
  items: WatchlistItem[];
  selectedItem: WatchlistItem | null;
  onSelect: (item: WatchlistItem) => void;
}) {
  return (
    <Card title="Watchlist Candidates" icon={<Target size={18} />} className="wide">
      {items.length === 0 ? (
        <EmptyState text="No watchlist candidates for the selected briefing." />
      ) : (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Setup</th>
                <th className="num">% Chg</th>
                <th className="num">Vol</th>
                <th className="num">Close</th>
                <th className="num">Score</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const key = `${item.symbol}-${item.setup_type}`;
                const isSelected =
                  selectedItem?.symbol === item.symbol &&
                  selectedItem?.setup_type === item.setup_type;
                return (
                  <tr
                    className={isSelected ? "selectedRow" : ""}
                    key={key}
                    onClick={() => onSelect(item)}
                  >
                    <td>
                      <button className="textButton" type="button">
                        {item.symbol}
                      </button>
                    </td>
                    <td>{setupLabel(item.setup_type, item.notes)}</td>
                    <td className="num">{formatNumber(item.pct_change)}%</td>
                    <td className="num">{formatNumber(item.volume_ratio, 1)}x</td>
                    <td className="num">{formatCurrency(item.close)}</td>
                    <td className="num">{formatNumber(item.score, 2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function CandidateDetailPanel({ 
  item, 
  accountSize, 
  apiBaseUrl, 
  date,
  onTradeOpened 
}: { 
  item: WatchlistItem | null;
  accountSize: number;
  apiBaseUrl: string;
  date: string;
  onTradeOpened: () => void;
}) {
  const [isExecuting, setIsExecuting] = useState(false);
  const [stopPrice, setStopPrice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  useEffect(() => {
    setIsExecuting(false);
    setStopPrice("");
  }, [item]);

  useEffect(() => {
    if (!item) { setCandles([]); return; }
    setChartLoading(true);
    fetch(`${apiBaseUrl}/ohlcv/${item.symbol}?days=90`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setCandles(data.candles ?? []))
      .catch(() => setCandles([]))
      .finally(() => setChartLoading(false));
  }, [item, apiBaseUrl]);

  if (!item) {
    return (
      <Card title="Candidate Detail" icon={<Target size={18} />}>
        <EmptyState text="Select a watchlist row to inspect the candidate." />
      </Card>
    );
  }

  const entryPrice = item.close ?? 0;
  const stopValue = Number(stopPrice);
  const diff = entryPrice - stopValue;
  // compute shares
  let shares = 0;
  if (stopValue > 0 && diff > 0 && accountSize > 0) {
    const riskAmount = accountSize * 0.01; // 1% risk
    shares = Math.floor(riskAmount / diff);
  }

  async function handleExecute(e: React.FormEvent) {
    e.preventDefault();
    if (shares <= 0) return;
    setIsSubmitting(true);
    try {
      const payload = {
        symbol: item!.symbol,
        setup_type: item!.setup_type,
        entry_date: date,
        entry_price: entryPrice,
        stop_price: stopValue,
        shares,
        grade: ""
      };
      
      const res = await fetch(`${apiBaseUrl}/trades/open`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to open trade");
      
      setIsExecuting(false);
      onTradeOpened();
    } catch (err) {
      alert("Error opening trade: " + String(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Card title="Candidate Detail" icon={<Target size={18} />}>
      {isExecuting ? (
        <form className="detailStack" onSubmit={handleExecute}>
          <div>
            <span className="label">Executing: {item.symbol}</span>
            <strong className="detailTitle">Entry at {formatCurrency(entryPrice)}</strong>
          </div>
          <Metric label="1% Risk Amount" value={formatCurrency(accountSize * 0.01)} />
          <label style={{display: "flex", flexDirection: "column", gap: "4px"}}>
            <span className="label">Stop Loss</span>
            <input 
              type="number" 
              step="0.05" 
              required 
              value={stopPrice} 
              onChange={e => setStopPrice(e.target.value)} 
              style={{ background: "var(--bg-card)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", borderRadius: "4px", padding: "4px" }}
            />
          </label>
          <Metric label="Computed Shares" value={shares.toString()} />
          <Metric label="Position Value" value={formatCurrency(shares * entryPrice)} />
          <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
            <button type="submit" disabled={isSubmitting || shares <= 0} style={{ fontWeight: "bold" }}>
              {isSubmitting ? "Opening..." : "Confirm Trade"}
            </button>
            <button type="button" onClick={() => setIsExecuting(false)}>Cancel</button>
          </div>
          {chartLoading ? (
            <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", paddingTop: "8px" }}>Loading chart…</div>
          ) : (
            <CandleChart candles={candles} entryPrice={entryPrice} stopPrice={stopValue > 0 ? stopValue : undefined} height={220} />
          )}
        </form>
      ) : (
        <div className="detailStack">
          <div>
            <span className="label">Symbol</span>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong className="detailTitle">{item.symbol}</strong>
              {item.close ? (
                <button 
                  type="button" 
                  onClick={() => setIsExecuting(true)}
                  style={{ background: "#4caf50", color: "#fff", border: "none", padding: "4px 8px", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}
                >
                  Execute ⚡
                </button>
              ) : null}
            </div>
          </div>
          <Metric label="Setup" value={setupLabel(item.setup_type, item.notes)} />
          <Metric label="Score" value={formatNumber(item.score, 2)} />
          <Metric label="Move" value={`${formatNumber(item.pct_change)}%`} />
          <Metric label="Volume" value={`${formatNumber(item.volume_ratio, 1)}x`} />
          <Metric label="Close" value={formatCurrency(item.close)} />
          <div className="notesBox">
            <span className="label">Notes</span>
            <p>{item.notes || "-"}</p>
          </div>
          {chartLoading ? (
            <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", paddingTop: "8px" }}>Loading chart…</div>
          ) : (
            <CandleChart candles={candles} height={240} />
          )}
        </div>
      )}
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
  const actionTypes = ["ALL", "TRAIL_TO_BREAKEVEN", "TIME_EXIT"];
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
            {actionType.replaceAll("_", " ")}
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
                <span>{trade.action_required.replaceAll("_", " ")}</span>
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

function OpenTradesPanel({ trades }: { trades: Trade[] }) {
  return (
    <Card title="Open Trades" icon={<Clock3 size={18} />} className="wide">
      {trades.length === 0 ? (
        <EmptyState text="No open trades are logged." />
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
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={trade.id}>
                  <td>
                    <strong>{trade.symbol}</strong>
                  </td>
                  <td>{trade.setup_type.replaceAll("_", " ")}</td>
                  <td className="num">{formatCurrency(trade.entry_price)}</td>
                  <td className="num">{formatCurrency(trade.stop_price)}</td>
                  <td className="num">{formatCurrency(trade.current_close)}</td>
                  <td className="num">{formatCurrency(trade.unrealized_pnl)}</td>
                  <td className="num">{formatNumber(trade.pct_gain, 2)}%</td>
                  <td>{trade.action_required.replaceAll("_", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function SummaryPanel({ summary }: { summary: TradeSummary | null }) {
  return (
    <Card title="Trade Summary" icon={<BarChart3 size={18} />}>
      {!summary ? (
        <EmptyState text="No closed-trade summary is available." />
      ) : (
        <div className="metricGrid compact">
          <Metric label="Closed" value={formatNumber(summary.total_trades, 0)} />
          <Metric label="Win Rate" value={`${formatNumber(summary.win_rate)}%`} />
          <Metric label="Avg Win" value={`${formatNumber(summary.avg_win_r, 2)}R`} />
          <Metric label="Avg Loss" value={`${formatNumber(summary.avg_loss_r, 2)}R`} />
          <Metric label="Expectancy" value={`${formatNumber(summary.expectancy_r, 2)}R`} />
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
  initialOpenTrades,
  initialSummary
}: DashboardClientProps) {
  const [briefing, setBriefing] = useState(initialBriefing);
  const [dates, setDates] = useState(initialDates?.items ?? []);
  const [openTrades, setOpenTrades] = useState(initialOpenTrades);
  const [actions, setActions] = useState(initialActions);
  const [summary, setSummary] = useState(initialSummary);
  const [selectedDate, setSelectedDate] = useState(initialBriefing?.date ?? "");
  const [selectedItem, setSelectedItem] = useState<WatchlistItem | null>(
    initialBriefing?.watchlist[0] ?? null
  );
  const [actionFilter, setActionFilter] = useState("ALL");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [accountSize, setAccountSize] = useState<number>(500000);

  useEffect(() => {
    const saved = localStorage.getItem("dhanustambha_account_size");
    if (saved) {
      setAccountSize(Number(saved));
    }
  }, []);

  const handleAccountSizeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = Number(e.target.value);
    setAccountSize(val);
    localStorage.setItem("dhanustambha_account_size", val.toString());
  };

  const apiUnavailable = !briefing && !openTrades && !actions && !summary;
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
      const [nextBriefing, nextDates, nextOpenTrades, nextActions, nextSummary] =
        await Promise.all([
          fetchJson<Briefing>(apiBaseUrl, briefingPath),
          fetchJson<DateList>(apiBaseUrl, "/briefing/dates"),
          fetchJson<TradeList>(apiBaseUrl, "/trades/open"),
          fetchJson<TradeList>(apiBaseUrl, "/trades/actions"),
          fetchJson<TradeSummary>(apiBaseUrl, "/trades/summary")
        ]);

      setBriefing(nextBriefing);
      setDates(nextDates.items);
      setOpenTrades(nextOpenTrades);
      setActions(nextActions);
      setSummary(nextSummary);
      setSelectedDate(nextBriefing.date);
      setSelectedItem(nextBriefing.watchlist[0] ?? null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Request failed");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Dhanustambha</h1>
          <p>NSE momentum dashboard</p>
        </div>
        <div className="topbarControls">
          <label className="dateControl">
            <span className="label">Account Size (₹)</span>
            <input
              type="number"
              value={accountSize}
              onChange={handleAccountSizeChange}
              step="10000"
              style={{ width: "110px", padding: "4px", background: "var(--bg-card)", color: "var(--text-main)", border: "1px solid var(--border-subtle)", borderRadius: "4px" }}
            />
          </label>
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
            title="Retry API requests"
            type="button"
          >
            <RefreshCw size={16} />
          </button>
          <div className={`statusPill ${apiUnavailable ? "offline" : "online"}`}>
            {apiUnavailable ? (
              <>
                <AlertTriangle size={16} /> API offline
              </>
            ) : (
              <>
                <CheckCircle2 size={16} /> API connected
              </>
            )}
          </div>
        </div>
      </header>

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
          <span className="label">Candidates</span>
          <strong>{briefing?.watchlist_count ?? 0}</strong>
        </div>
        <div>
          <span className="label">Open trades</span>
          <strong>{openTrades?.count ?? 0}</strong>
        </div>
        <div>
          <span className="label">Actions</span>
          <strong>{actions?.count ?? 0}</strong>
        </div>
      </div>

      <section className="grid">
        <MarketPanel market={briefing?.market ?? null} />
        <TradeActionsPanel
          filter={actionFilter}
          onFilterChange={setActionFilter}
          trades={actions?.items ?? []}
        />
        <SummaryPanel summary={summary} />
        <WatchlistPanel
          items={briefing?.watchlist ?? []}
          onSelect={setSelectedItem}
          selectedItem={selectedItem}
        />
        <CandidateDetailPanel 
          item={selectedItem}
          accountSize={accountSize}
          apiBaseUrl={apiBaseUrl}
          date={briefing?.date || selectedDate}
          onTradeOpened={() => loadDashboard(selectedDate)}
        />
        <OpenTradesPanel trades={openTrades?.items ?? []} />
      </section>

      <footer>
        <TrendingUp size={16} />
        <span>Read-only view backed by {apiBaseUrl}</span>
        <span className="footerFilter">
          <Filter size={14} /> {actionFilter.replaceAll("_", " ")}
        </span>
      </footer>
    </main>
  );
}
