'use client';

import { useState, useEffect, useMemo } from 'react';
import type { Briefing, DateList, WatchlistItem, TradeQuote } from '../../types/api';
import { formatNumber, formatCurrency, setupLabel } from '../../lib/format';
import { fetchJson } from '../../lib/api';
import { useAccountSize } from '../../hooks/useAccountSize';
import Card from '../components/ui/Card';
import EmptyState from '../components/ui/EmptyState';
import Metric from '../components/ui/Metric';
import CandleChart, { type Candle } from '../components/CandleChart';
import { Target, AlertTriangle, RefreshCw } from 'lucide-react';
import Link from 'next/link';
import LiveScanController from "../components/LiveScanController";

const CHART_TIMEFRAMES = [
  { label: "3M", days: 90 },
  { label: "6M", days: 180 },
  { label: "1Y", days: 365 },
] as const;

type ScannerClientProps = {
  apiBaseUrl: string;
  initialBriefing: Briefing | null;
  initialDates: DateList | null;
};

function WatchlistPanel({
  items,
  selectedItem,
  onSelect,
  onExecute,
  livePrices
}: {
  items: WatchlistItem[];
  selectedItem: WatchlistItem | null;
  onSelect: (item: WatchlistItem) => void;
  onExecute: (item: WatchlistItem) => void;
  livePrices: Record<string, { price: number; is_cached: boolean }>;
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
                <th className="num">LTP</th>
                <th className="num">Score</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const key = `${item.symbol}-${item.setup_type}`;
                const isSelected =
                  selectedItem?.symbol === item.symbol &&
                  selectedItem?.setup_type === item.setup_type;
                const live = livePrices[item.symbol];

                return (
                  <tr
                    className={isSelected ? "selectedRow" : ""}
                    key={key}
                    onClick={() => onSelect(item)}
                  >
                    <td>
                      <Link href={`/stock/${item.symbol}`} className="textButton">
                        {item.symbol}
                      </Link>
                    </td>
                    <td>{setupLabel(item.setup_type, item.notes)}</td>
                    <td className="num">{formatNumber(item.pct_change)}%</td>
                    <td className="num">{formatNumber(item.volume_ratio, 1)}x</td>
                    <td className="num">{formatCurrency(item.close)}</td>
                    <td className={`num ${live ? 'livePrice' : ''}`}>
                      {live ? formatCurrency(live.price) : '-'}
                    </td>
                    <td className="num">{formatNumber(item.score, 2)}</td>
                    <td>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          onExecute(item);
                        }}
                        style={{ background: "#4caf50", color: "#fff", border: "none", padding: "2px 6px", borderRadius: "4px", cursor: "pointer", fontSize: "11px", fontWeight: "bold" }}
                      >
                        Execute
                      </button>
                    </td>
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
  livePrice,
  isExecuting,
  setIsExecuting,
  onTradeOpened 
}: { 
  item: WatchlistItem | null;
  accountSize: number;
  apiBaseUrl: string;
  date: string;
  livePrice?: number;
  isExecuting: boolean;
  setIsExecuting: (val: boolean) => void;
  onTradeOpened: () => void;
}) {
  const [stopPrice, setStopPrice] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [quote, setQuote] = useState<TradeQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [chartDays, setChartDays] = useState<number>(90);
  const [chartHeight, setChartHeight] = useState<number>(420);

  useEffect(() => {
    setStopPrice("");
    setQuote(null);
    setQuoteError(null);
  }, [item]);

  useEffect(() => {
    if (isExecuting && item && !stopPrice) {
      setStopPrice(defaultStopPrice(item));
    }
  }, [isExecuting, item]);

  useEffect(() => {
    if (!item) { setCandles([]); return; }
    setChartLoading(true);
    fetch(`${apiBaseUrl}/ohlcv/${item.symbol}?days=${chartDays}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setCandles(data.candles ?? []))
      .catch(() => setCandles([]))
      .finally(() => setChartLoading(false));
  }, [item, apiBaseUrl, chartDays]);

  const entryPrice = livePrice || item?.close || 0;
  const stopValue = Number(stopPrice);

  function defaultStopPrice(nextItem: WatchlistItem): string {
    const stopPctBySetup: Record<string, number> = {
      MOMENTUM_BURST: 2.5,
      EP: 4.0,
      EPISODIC_PIVOT: 4.0,
      TREND_INTENSITY: 1.5,
    };
    const stopPct = stopPctBySetup[nextItem.setup_type] ?? 4.0;
    const close = nextItem.close ?? 0;
    const rawStop = close * (1 - stopPct / 100);
    const roundedToTick = Math.round(rawStop * 20) / 20;
    return roundedToTick.toFixed(2);
  }

  useEffect(() => {
    if (!isExecuting || !item || entryPrice <= 0 || !stopPrice || accountSize <= 0) {
      setQuote(null);
      setQuoteError(null);
      return;
    }

    const controller = new AbortController();
    setQuoteLoading(true);
    setQuoteError(null);
    fetch(`${apiBaseUrl}/trades/quote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: item.symbol,
        setup_type: item.setup_type,
        entry_date: date,
        entry_price: entryPrice,
        stop_price: Number(stopPrice),
        account_size: accountSize
      }),
      signal: controller.signal
    })
      .then(async (response) => {
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? `Quote failed: ${response.status}`);
        }
        return response.json() as Promise<TradeQuote>;
      })
      .then((payload) => {
        setQuote(payload);
        setQuoteError(null);
      })
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") {
          return;
        }
        setQuote(null);
        setQuoteError(err instanceof Error ? err.message : "Quote failed");
      })
      .finally(() => setQuoteLoading(false));

    return () => controller.abort();
  }, [accountSize, apiBaseUrl, date, entryPrice, isExecuting, item, stopPrice]);

  if (!item) {
    return (
      <Card title="Candidate Detail" icon={<Target size={18} />}>
        <EmptyState text="Select a watchlist row to inspect the candidate." />
      </Card>
    );
  }

  async function handleExecute(e: React.FormEvent) {
    e.preventDefault();
    if (!quote || quote.shares <= 0) return;
    setIsSubmitting(true);
    try {
      const payload = {
        symbol: item!.symbol,
        setup_type: item!.setup_type,
        entry_date: date,
        entry_price: entryPrice,
        stop_price: stopValue,
        account_size: accountSize,
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

  const timeframeLabel =
    CHART_TIMEFRAMES.find((timeframe) => timeframe.days === chartDays)?.label ?? "Custom";

  function renderChartControls() {
    return (
      <div className="chartToolbar" style={{ gridColumn: "1 / -1" }}>
        <div className="timeframeBar">
          {CHART_TIMEFRAMES.map((timeframe) => (
            <button
              key={timeframe.label}
              type="button"
              className={`timeframeBtn ${chartDays === timeframe.days ? "active" : ""}`}
              onClick={() => setChartDays(timeframe.days)}
            >
              {timeframe.label}
            </button>
          ))}
        </div>
        <div className="chartResizeControls">
          <button
            type="button"
            className="timeframeBtn"
            aria-label="Compact Chart"
            onClick={() => setChartHeight((value) => Math.max(320, value - 80))}
          >
            Compact Chart
          </button>
          <button
            type="button"
            className="timeframeBtn"
            aria-label="Expand Chart"
            onClick={() => setChartHeight((value) => Math.min(720, value + 80))}
          >
            Expand Chart
          </button>
        </div>
      </div>
    );
  }

  return (
    <Card title="Candidate Detail" icon={<Target size={18} />}>
      {isExecuting ? (
        <form className="detailStack" onSubmit={handleExecute}>
          <div>
            <span className="label">Executing: {item.symbol}</span>
            <strong className="detailTitle">Entry at {formatCurrency(entryPrice)}</strong>
          </div>
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
          <Metric label="Market Regime" value={quote?.market_verdict ?? "-"} />
          <Metric label="Risk Budget" value={quote ? `${formatCurrency(quote.risk_amount)} (${formatNumber(quote.risk_pct, 2)}%)` : "-"} />
          <Metric label="Computed Shares" value={quoteLoading ? "Computing..." : quote ? String(quote.shares) : "-"} />
          <Metric label="Position Value" value={quote ? formatCurrency(quote.position_value) : "-"} />
          <Metric label="R Unit" value={quote ? formatCurrency(quote.r_unit) : "-"} />
          <Metric label="Max Position" value={quote ? formatCurrency(quote.max_position_value) : "-"} />
          {quoteError && (
            <div className="errorBanner" style={{ gridColumn: "1 / -1", marginBottom: 0 }}>
              <AlertTriangle size={16} />
              <span>{quoteError}</span>
            </div>
          )}
          <div style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
            <button type="submit" disabled={isSubmitting || quoteLoading || !quote || quote.shares <= 0} style={{ fontWeight: "bold" }}>
              {isSubmitting ? "Opening..." : "Confirm Trade"}
            </button>
            <button type="button" onClick={() => setIsExecuting(false)}>Cancel</button>
          </div>
          {renderChartControls()}
          {chartLoading ? (
            <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", paddingTop: "8px" }}>Loading chart...</div>
          ) : (
            <CandleChart
              candles={candles}
              entryPrice={entryPrice}
              stopPrice={stopValue > 0 ? stopValue : undefined}
              setupType={item.setup_type}
              signalDate={date}
              height={chartHeight}
              title={`${item.symbol} Entry Map`}
              subtitle={`${timeframeLabel} window`}
            />
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
                  onClick={() => {
                    setStopPrice(defaultStopPrice(item));
                    setIsExecuting(true);
                  }}
                  style={{ background: "#4caf50", color: "#fff", border: "none", padding: "4px 8px", borderRadius: "4px", cursor: "pointer", fontWeight: "bold" }}
                >
                  Execute
                </button>
              ) : null}
            </div>
          </div>
          <Metric label="Setup" value={setupLabel(item.setup_type, item.notes)} />
          <Metric label="Score" value={formatNumber(item.score, 2)} />
          <Metric label="Move" value={`${formatNumber(item.pct_change)}%`} />
          <Metric label="Volume" value={`${formatNumber(item.volume_ratio, 1)}x`} />
          <Metric label="EOD Close" value={formatCurrency(item.close)} />
          <Metric label="Live Price (LTP)" value={livePrice ? formatCurrency(livePrice) : "-"} highlight={!!livePrice} />
          <div className="notesBox">
            <span className="label">Notes</span>
            <p>{item.notes || "-"}</p>
          </div>
          {renderChartControls()}
          {chartLoading ? (
            <div style={{ fontSize: "11px", color: "var(--text-muted, #64748b)", paddingTop: "8px" }}>Loading chart...</div>
          ) : (
            <CandleChart
              candles={candles}
              setupType={item.setup_type}
              signalDate={date}
              height={chartHeight}
              title={`${item.symbol} Setup Map`}
              subtitle={`${timeframeLabel} window`}
            />
          )}
        </div>
      )}
    </Card>
  );
}


export default function ScannerClient({ apiBaseUrl, initialBriefing, initialDates }: ScannerClientProps) {
  const [briefing, setBriefing] = useState(initialBriefing);
  const [dates, setDates] = useState(initialDates?.items ?? []);
  const [selectedDate, setSelectedDate] = useState(initialBriefing?.date ?? '');
  const [selectedItem, setSelectedItem] = useState<WatchlistItem | null>(initialBriefing?.watchlist[0] ?? null);
  const [isExecuting, setIsExecuting] = useState(false);
  const [livePrices, setLivePrices] = useState<Record<string, { price: number; is_cached: boolean }>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Bug 1 fix: filterType state now stores the canonical setup_type value ('EPISODIC_PIVOT', not 'EP')
  const [filterType, setFilterType] = useState('ALL');
  const [accountSize] = useAccountSize();

  // Stream H: Live Price Polling
  useEffect(() => {
    if (!briefing || briefing.watchlist.length === 0) return;
    
    let isMounted = true;
    const symbols = encodeURIComponent(Array.from(new Set(briefing.watchlist.map(i => i.symbol))).join(','));
    
    async function fetchLive() {
      try {
        const data = await fetchJson<{ items: typeof livePrices }>(apiBaseUrl, `/market/prices?symbols=${symbols}`);
        if (isMounted) setLivePrices(data.items);
      } catch (err) {
        console.warn('Live price fetch failed:', err);
      }
    }

    fetchLive();
    const timer = setInterval(fetchLive, 60000); // 1 minute refresh
    return () => { isMounted = false; clearInterval(timer); };
  }, [briefing, apiBaseUrl]);

  const knownDates = useMemo(() => {
    if (selectedDate && !dates.includes(selectedDate)) return [selectedDate, ...dates];
    return dates;
  }, [dates, selectedDate]);

  const filteredWatchlist = useMemo(() => {
    if (!briefing) return [];
    if (filterType === 'ALL') return briefing.watchlist;
    return briefing.watchlist.filter(item => item.setup_type === filterType);
  }, [briefing, filterType]);

  async function loadScanners(nextDate: string) {
    setIsLoading(true);
    setError(null);
    try {
      const briefingPath = nextDate ? `/briefing/${nextDate}` : '/briefing/latest';
      const [nextBriefing, nextDates] = await Promise.all([
        fetchJson<Briefing>(apiBaseUrl, briefingPath),
        fetchJson<DateList>(apiBaseUrl, '/briefing/dates')
      ]);
      setBriefing(nextBriefing);
      setDates(nextDates.items);
      setSelectedDate(nextBriefing.date);
      setSelectedItem(nextBriefing.watchlist[0] ?? null);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Request failed');
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Scanners</h1>
          <p>{filteredWatchlist.length} candidates found</p>
        </div>
        <div className="topbarControls">
          <LiveScanController apiBaseUrl={apiBaseUrl} onComplete={() => loadScanners('')} />
          <label className="dateControl">
            <span className="label">Briefing date</span>
            <select disabled={knownDates.length === 0 || isLoading} onChange={(e) => loadScanners(e.target.value)} value={selectedDate}>
              {knownDates.length === 0 ? <option value="">No dates</option> : knownDates.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <button className="iconButton" disabled={isLoading} onClick={() => loadScanners(selectedDate)}><RefreshCw size={16} /></button>
        </div>
      </header>

      {error && (
        <div className="errorBanner">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button onClick={() => loadScanners(selectedDate)} type="button">Retry</button>
        </div>
      )}

      {/* Bug 1 fix: filter tab values match canonical DB setup_type strings.
          'EP' is only the display label — the actual filter value is 'EPISODIC_PIVOT'. */}
      <div className="segmented" style={{ maxWidth: '600px', marginBottom: '20px', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        {([
          { value: 'ALL',             label: 'ALL' },
          { value: 'MOMENTUM_BURST',  label: 'MB' },
          { value: 'EPISODIC_PIVOT',  label: 'EP' },
          { value: 'TREND_INTENSITY', label: 'TI' },
        ] as const).map(({ value, label }) => (
          <button key={value} className={filterType === value ? 'active' : ''} onClick={() => setFilterType(value)} type="button">{label}</button>
        ))}
      </div>

      <section className="grid">
        <WatchlistPanel 
          items={filteredWatchlist} 
          selectedItem={selectedItem} 
          onSelect={(i) => { setSelectedItem(i); setIsExecuting(false); }} 
          onExecute={(i) => { setSelectedItem(i); setIsExecuting(true); }}
          livePrices={livePrices}
        />
        <CandidateDetailPanel 
          item={selectedItem} 
          accountSize={accountSize} 
          apiBaseUrl={apiBaseUrl} 
          date={briefing?.date || selectedDate} 
          livePrice={selectedItem ? livePrices[selectedItem.symbol]?.price : undefined}
          isExecuting={isExecuting}
          setIsExecuting={setIsExecuting}
          onTradeOpened={() => { loadScanners(selectedDate); setIsExecuting(false); }} 
        />
      </section>
    </main>
  );
}
