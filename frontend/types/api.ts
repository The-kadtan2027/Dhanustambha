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
  exit_price?: number | null;
  pnl?: number | null;
  status?: string;
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

export type TradeQuote = {
  valid: boolean;
  shares: number;
  position_value: number;
  risk_amount: number;
  r_unit: number;
  risk_pct: number;
  max_position_value: number;
  market_verdict: string;
};
