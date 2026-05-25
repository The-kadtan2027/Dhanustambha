# Chart Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade price and breadth charts so they are more intuitive, more decision-oriented, and user-resizable on the scanner and market surfaces.

**Architecture:** Keep the existing chart libraries and improve the shared chart contract instead of replacing the stack. Centralize price-chart behavior in the shared candlestick component, add lightweight parent-level timeframe/resize controls, and make the market breadth page threshold-aware and resizable without changing the backend contract.

**Tech Stack:** Next.js App Router, React, TypeScript, lightweight-charts, Recharts, Playwright.

---

### Task 1: Add browser tests for chart controls and resize behavior

**Files:**
- Modify: `frontend/tests/navigation.spec.ts`

- [ ] Add a failing Playwright test that opens the scanner page, selects a candidate, and checks that timeframe buttons and chart resize controls render.
- [ ] Run the focused Playwright test to verify it fails because the new controls do not exist yet.
- [ ] Add a failing Playwright test that opens the market page and checks for breadth resize controls plus threshold-oriented chart labels.
- [ ] Run the focused Playwright test to verify it fails for the expected reason.

### Task 2: Upgrade the shared price chart component

**Files:**
- Modify: `frontend/app/components/CandleChart.tsx`
- Modify: `frontend/app/globals.css`

- [ ] Add component props for chart title metadata, last-price summary mode, and parent-controlled visual density where needed.
- [ ] Improve the legend, summary band, signal emphasis, and risk presentation while keeping current entry/stop overlays.
- [ ] Preserve the existing crosshair readout but make the default state informative even before hover.
- [ ] Add CSS hooks needed for the new shared chart header and resizable container styling.

### Task 3: Add timeframe and resize controls to scanner charts

**Files:**
- Modify: `frontend/app/scanners/scanner-client.tsx`
- Modify: `frontend/app/globals.css`

- [ ] Add scanner detail state for chart timeframe and chart height.
- [ ] Fetch OHLCV using the selected timeframe window instead of a fixed 90-day request.
- [ ] Add compact timeframe controls and larger-smaller chart actions for the candidate detail panel.
- [ ] Keep execute-mode and inspect-mode charts aligned on the same controls.

### Task 4: Improve Trade Book and Stock Detail chart integration

**Files:**
- Modify: `frontend/app/trades/trade-client.tsx`
- Modify: `frontend/app/components/PositionCard.tsx`
- Modify: `frontend/app/stock/[symbol]/stock-detail-client.tsx`

- [ ] Add better chart summary context in trade-management flows without expanding scope into new backend features.
- [ ] Keep stock detail timeframe controls as the deepest analysis surface and align the chart header language with scanner/trade pages.
- [ ] Adjust position-card chart framing so it remains readable in constrained card width.

### Task 5: Make market breadth charts clearer and resizable

**Files:**
- Modify: `frontend/app/market/market-client.tsx`
- Modify: `frontend/app/globals.css`

- [ ] Add resize state for the main breadth panels.
- [ ] Make MA20 and MA50 panels visually reflect the offensive/defensive thresholds.
- [ ] Strengthen zero-line and positive-negative interpretation for net A/D and net highs-lows.
- [ ] Improve chart headers and helper labels so the page reads as a regime dashboard, not a generic chart collection.

### Task 6: Verify end-to-end

**Files:**
- Modify if needed: `frontend/tests/navigation.spec.ts`

- [ ] Run `cmd /c npm run build` inside `frontend` and confirm it succeeds.
- [ ] Run the relevant Playwright spec(s) and confirm the new chart behavior passes.
- [ ] If any backend assumptions changed, run targeted `pytest` coverage before closing the task.
