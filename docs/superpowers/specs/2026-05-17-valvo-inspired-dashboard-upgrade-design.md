# Valvo-Inspired Dashboard Visual Upgrade

Transform Dhanustambha's functional but plain UI into a polished, Valvo Intelligence–level trading dashboard across three sub-projects.

## Reference

Three screenshots from [Valvo Intelligence](https://valvo.in):
1. **Position Manager** — card grid with embedded charts and portfolio summary bar
2. **Stock Detail** — full interactive chart with trade summary sidebar
3. **Market Breadth** — regime badge, A/D ratio bars, historical breadth sparklines

## Sub-Project A: Position Manager Card Grid

**Replaces:** The table-only `/trades` page.

### What Changes

**New backend endpoint: `GET /trades/portfolio`**  
Aggregates open trade data into portfolio-level metrics:
- `total_invested` — sum of (entry_price × shares) for all open trades
- `days_pnl` — sum of price change today × shares (requires previous close)
- `total_pnl` — sum of unrealized P&L across all positions
- `open_risk` — sum of (entry_price - stop_price) × shares
- `locked_profit` — sum of (stop_price - entry_price) × shares for trades where stop > entry

Computed from existing `build_open_trade_status()`, extended with `get_previous_close()` for day P&L.

**New frontend: position card grid**
Each open trade renders as a card containing:
- Symbol name, setup type badge, holding days
- Key metrics inline: position size (₹), % gain from entry, R-multiple gain, unrealized P&L (₹)
- Embedded `CandleChart` (compact ~220px height) with entry + stop overlay lines
- Bottom row: Entry price, Stop price, CMP (current market price)
- Color-coded: green for winners, red for losers

**Portfolio summary bar** (replaces current empty topbar):
5-cell hero band: % Invested | Day's P&L | Total P&L | Open Risk | Locked Profit

**View toggles**: Card Grid (default, with charts) | Table (existing behavior)  
**Tabs**: Active | Closed (reuses existing `/trades/closed` endpoint)

### Data Flow
```
GET /trades/open → existing enriched data → card grid
GET /trades/portfolio → new aggregate endpoint → hero band
GET /ohlcv/{symbol}?days=90 → existing → CandleChart per card
```

### Existing Assets Reused
- `CandleChart` component (lightweight-charts v5) — pass smaller height
- `build_open_trade_status()` already computes current_close, unrealized_pnl, pct_gain, days_held
- `Trade` type in `types/api.ts`
- `formatCurrency`, `formatNumber` from `lib/format.ts`

---

## Sub-Project B: Stock Detail View

**New route:** `/stock/[symbol]`  
Accessible when clicking any symbol in Scanners, Trade Book, or Journal.

### What Changes

**Full-screen chart view** with:
- Large `CandleChart` (~500px) with MA20/MA50 overlays, entry/stop lines
- Entry/exit price markers if the stock has an associated trade
- SMA values displayed in the chart footer (like Valvo's bottom bar)

**Trade summary sidebar** (right panel, ~300px):
- If the symbol has an open trade: Unrealized P&L, R-Multiple, Entry → CMP, Shares, Days Held, Setup Type
- If the symbol has closed trade(s): Realized P&L, R-Multiple, Lifetime return, Sell History log
- If no trade: just the stock info and latest OHLCV stats

**New backend endpoint: `GET /trades/by-symbol/{symbol}`**  
Returns all trades (open + closed) for a specific symbol to populate the sidebar.

### Data Flow
```
GET /ohlcv/{symbol}?days=365 → CandleChart (1Y default)
GET /trades/by-symbol/{symbol} → trade sidebar
```

### Timeframe Selector
Buttons: 3M | 6M | 1Y | 2Y | All — changes the `days` param on OHLCV fetch.

---

## Sub-Project C: Enhanced Market Breadth

**Upgrades:** The existing `BreadthGauges` component on the Dashboard.

### What Changes

**New backend: advance/decline in breadth history**  
The existing `get_breadth_history()` already returns `advancing`/`declining` per day. No new endpoint needed — just use the existing fields.

**Regime label badge** — "Moderately Bullish" / "Bearish" etc.:
Derived from the verdict + breadth thresholds:
- OFFENSIVE + MA20 > 65% → "Strongly Bullish"  
- OFFENSIVE → "Moderately Bullish"  
- DEFENSIVE → "Cautious"  
- AVOID + MA20 < 35% → "Bearish"  
- AVOID → "Cautious / Avoid"

**Advance/Decline section**:
- Large advancing/declining counts with green/red coloring
- Ratio display (e.g., "1.84 : 1")
- Progress bar showing advancing vs declining as proportional segments
- Daily Advances-Declines bar chart (Recharts `BarChart`, last 30 days)

**Historical breadth sparkline cards** (3 across):
- % Above 20 EMA (MA20) — with line chart sparkline and current value
- % Above 50 EMA (MA50) — same pattern
- New Highs vs New Lows — net H/L sparkline

Each card: small title, large value, 30-day sparkline, trend icon (↑/↓).

**Timeframe selector**: 1M | 3M | 6M — changes `days` parameter on breadth history fetch. Currently hardcoded to 60.

### Existing Assets Reused
- `BreadthGauges` component — will be refactored/replaced
- `get_breadth_history()` already returns all needed fields
- Recharts already installed (`AreaChart`, can add `BarChart`)
- `Market` type in `types/api.ts` already has all breadth fields

---

## Design Decisions

### 1. Light-mode palette (keep existing)
The current `globals.css` uses a clean light-mode design system. The Valvo screenshots show a light theme too. We stay with the existing palette and refine card styling.

### 2. CandleChart reuse
The existing `CandleChart` already uses `lightweight-charts` v5 with MA overlays and entry/stop price lines. For position cards, we pass `height={220}`. For stock detail, `height={500}`.

### 3. CSS-first approach
New layout classes go in `globals.css`. No new CSS framework. Position card grid uses `display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr))`.

### 4. Progressive loading for charts
Position cards render immediately with metrics. Each card's chart loads independently via `GET /ohlcv/{symbol}?days=90` — same pattern already used in scanner-client.

---

## File Impact Summary

### Backend (Python)
| File | Change |
|------|--------|
| `src/trade/log.py` | Add `build_portfolio_summary()`, `get_previous_close_for_trades()` |
| `src/api/main.py` | Add `GET /trades/portfolio`, `GET /trades/by-symbol/{symbol}` |
| `src/ingestion/store.py` | Add `get_previous_close()` helper |

### Frontend (TypeScript/React)
| File | Change |
|------|--------|
| `types/api.ts` | Add `PortfolioSummary`, `TradesBySymbol` types |
| `app/trades/trade-client.tsx` | Complete rewrite → card grid + table toggle |
| `app/stock/[symbol]/page.tsx` | **New** server page |
| `app/stock/[symbol]/stock-detail-client.tsx` | **New** client component |
| `app/components/PositionCard.tsx` | **New** — single trade card with embedded chart |
| `app/components/PortfolioBar.tsx` | **New** — 5-metric hero band |
| `app/components/BreadthGauges.tsx` | Rewrite → regime badge, A/D bars, sparklines, timeframe toggle |
| `app/globals.css` | Add position card grid, stock detail, breadth section styles |

### Tests
| File | Change |
|------|--------|
| `tests/test_api.py` | Add tests for `/trades/portfolio`, `/trades/by-symbol/{symbol}` |
| `tests/navigation.spec.ts` | Add stock detail route test, trade book card grid verification |

---

## Verification Plan

### Automated Tests
```bash
# Python backend tests
cd d:\antigravity\Dhanustambha
"C:\Program Files\Python312\python.exe" -m pytest tests/test_api.py -v

# Playwright E2E tests
cd d:\antigravity\Dhanustambha\frontend
npx playwright test tests/navigation.spec.ts
```

### Manual Verification
1. Start backend: `"C:\Program Files\Python312\python.exe" -m uvicorn src.api.main:app --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Verify:
   - `/trades` shows card grid with embedded charts + portfolio summary bar
   - Clicking a symbol navigates to `/stock/{symbol}` detail view
   - Dashboard breadth section shows regime badge, A/D bars, sparklines
   - View toggle switches between card grid and table on `/trades`
