import type { PortfolioSummary } from "../../types/api";
import { formatCurrency } from "../../lib/format";

function Cell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ padding: "14px 20px" }}>
      <span className="label" style={{ color: "rgba(255,255,255,0.6)" }}>{label}</span>
      <strong style={{ display: "block", fontSize: 24, marginTop: 6, color: color ?? "white" }}>
        {value}
      </strong>
    </div>
  );
}

export default function PortfolioBar({ summary }: { summary: PortfolioSummary | null }) {
  if (!summary) return null;
  const pnlColor = summary.total_pnl >= 0 ? "#4ade80" : "#f87171";
  return (
    <div className="heroBand" style={{ gridTemplateColumns: "repeat(5, minmax(0, 1fr))", marginBottom: 20 }}>
      <Cell label="Open Positions" value={String(summary.trade_count)} />
      <Cell label="Total P&L" value={formatCurrency(summary.total_pnl)} color={pnlColor} />
      <Cell label="Total Invested" value={formatCurrency(summary.total_invested)} />
      <Cell label="Open Risk" value={formatCurrency(summary.open_risk)} color="#fbbf24" />
      <Cell label="Locked Profit" value={formatCurrency(summary.locked_profit)} color="#4ade80" />
    </div>
  );
}
