'use client';

import { useState } from 'react';
import type { Trade, TradeSummary } from '../../types/api';
import { formatNumber, formatCurrency, setupLabel } from '../../lib/format';
import SummaryPanel from '../components/ui/SummaryPanel';
import Card from '../components/ui/Card';
import { Activity, BookOpen, AlertTriangle } from 'lucide-react';
import Link from 'next/link';

type JournalClientProps = {
  apiBaseUrl: string;
  initialClosedTrades: { count: number; items: Trade[] } | null;
  initialSummary: TradeSummary | null;
};

export default function JournalClient({ apiBaseUrl, initialClosedTrades, initialSummary }: JournalClientProps) {
  const [trades, setTrades] = useState(initialClosedTrades?.items ?? []);
  const [summary, setSummary] = useState(initialSummary);
  const [activeTrade, setActiveTrade] = useState<Trade | null>(null);
  
  // Review Form State
  const [entryRule, setEntryRule] = useState<boolean>(true);
  const [exitRule, setExitRule] = useState<boolean>(true);
  const [whatToImprove, setWhatToImprove] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  
  const today = new Date().toISOString().split('T')[0];

  function handleSelect(trade: Trade) {
    setActiveTrade(trade);
    setEntryRule(true);
    setExitRule(true);
    setWhatToImprove('');
    setSuccessMsg('');
  }

  async function submitReview(e: React.FormEvent) {
    e.preventDefault();
    if (!activeTrade) return;
    setIsSubmitting(true);
    setSuccessMsg('');
    try {
      const payload = {
        entry_rule_followed: entryRule,
        exit_rule_followed: exitRule,
        what_to_improve: whatToImprove,
        review_date: today
      };
      
      const res = await fetch(`${apiBaseUrl}/trades/${activeTrade.id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Failed to submit review");
      setSuccessMsg("Review saved successfully.");
    } catch (err) {
      alert("Error: " + String(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <h1>Review Journal</h1>
          <p>Closed trades analysis</p>
        </div>
      </header>

      <section className="grid">
        <SummaryPanel summary={summary} />
        
        <Card title="Closed Trades" icon={<Activity size={18} />} className="wide">
          {trades.length === 0 ? (
            <div className="empty">No closed trades available for review.</div>
          ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Setup</th>
                  <th className="num">Entry</th>
                  <th className="num">Exit</th>
                  <th className="num">P&L</th>
                  <th className="num">Gain</th>
                  <th className="num">Days Held</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} onClick={() => handleSelect(t)} className={activeTrade?.id === t.id ? "selectedRow" : ""} style={{cursor: "pointer"}}>
                    <td><Link href={`/stock/${t.symbol}`} style={{ fontWeight: 700, color: "var(--blue)" }}>{t.symbol}</Link></td>
                    <td>{t.setup_type}</td>
                    <td className="num">{formatCurrency(t.entry_price)}</td>
                    <td className="num">{formatCurrency(t.exit_price ?? t.current_close)}</td>
                    <td className="num" style={{color: (t.pnl ?? t.unrealized_pnl ?? 0) >= 0 ? "var(--green)" : "var(--red)"}}>{formatCurrency(t.pnl ?? t.unrealized_pnl)}</td>
                    <td className="num">{formatNumber(t.pct_gain)}%</td>
                    <td className="num">{t.days_held ?? "-"}</td>
                    <td>{t.status?.replace('_', ' ') ?? "CLOSED"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          )}
        </Card>

        {activeTrade && (
          <Card title={`Journal: ${activeTrade.symbol}`} icon={<BookOpen size={18} />}>
             <form className="detailStack" onSubmit={submitReview}>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", gridColumn: "1 / -1" }}>
                  <input type="checkbox" checked={entryRule} onChange={e => setEntryRule(e.target.checked)} />
                  <span>Entry criteria strictly followed</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "8px", gridColumn: "1 / -1" }}>
                  <input type="checkbox" checked={exitRule} onChange={e => setExitRule(e.target.checked)} />
                  <span>Exit trailing limits strictly followed</span>
                </label>
                <label style={{ gridColumn: "1 / -1", display: "grid", gap: "4px" }}>
                  <span>Review Notes / Observations</span>
                  <textarea value={whatToImprove} onChange={e => setWhatToImprove(e.target.value)} rows={4} required style={{ background: "var(--panel-muted)", border: "1px solid var(--line)", padding: "8px", borderRadius: "4px", color: "inherit", fontFamily: "inherit" }} />
                </label>
                {successMsg && <span style={{color: "var(--green)", fontWeight: 600}}>{successMsg}</span>}
                <button type="submit" disabled={isSubmitting} style={{ gridColumn: "1 / -1", padding: "8px", background: "var(--blue)", color: "white", border: "none", borderRadius: "4px", fontWeight: "bold" }}>
                  {isSubmitting ? "Saving..." : "Save Review"}
                </button>
             </form>
          </Card>
        )}
      </section>
    </main>
  );
}
