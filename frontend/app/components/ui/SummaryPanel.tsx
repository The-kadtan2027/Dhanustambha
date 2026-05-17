import type { TradeSummary } from '../../../types/api';
import { formatNumber } from '../../../lib/format';
import Card from './Card';
import EmptyState from './EmptyState';
import Metric from './Metric';
import { BarChart3 } from 'lucide-react';

export default function SummaryPanel({ summary }: { summary: TradeSummary | null }) {
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

