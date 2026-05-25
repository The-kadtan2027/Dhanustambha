# Chart Usability Design

**Date:** 2026-05-24

## Goal

Improve the usefulness and intuitiveness of both price charts and market breadth charts across the app so users can make faster entry, exit, and regime decisions with less visual friction.

## Scope

- Shared price chart used in Scanners, Trade Book, Position Cards, and Stock Detail
- Dedicated market breadth charts on the Market Monitor page
- Scanner page and Market page chart containers
- Dashboard-adjacent chart surfaces that already consume the shared chart component

## Problems To Solve

1. Price charts are visually readable but do not expose enough decision context.
2. Chart behavior is inconsistent across pages.
3. Market breadth charts show history but do not clearly encode threshold meaning or regime interpretation.
4. Users cannot adapt chart space to the task at hand.

## Design

### Shared Price Chart

The shared candlestick component will become the source of truth for chart behavior. It will keep the existing lightweight-charts foundation and add:

- Stronger top summary band for last candle / crosshair candle
- Clear legend for MA20, MA50, signal, entry, and stop
- Optional timeframe controls supplied by parent views
- Optional support and range metadata derived from the visible candle set
- Better visual contrast for volume, signal marker, and risk context
- Resizable chart wrapper support through parent-controlled height

### Scanner / Trade / Stock Detail Integration

Scanner detail, trade management, position cards, and stock detail will use the same chart contract. Parent views will provide:

- Chosen timeframe window
- Chosen chart height
- Resize controls where appropriate
- Contextual labels around setup, risk, and signal date

### Market Breadth

The market page will keep Recharts but shift from generic spark panels to more decision-oriented views:

- Threshold-aware MA20 and MA50 trend panels
- Explicit zero-line / positive-negative emphasis for net highs-lows and advance-decline bars
- Clear regime helper text tied to stored breadth thresholds
- Resize controls so the user can expand the most relevant breadth panel

## Data Model Impact

No database or API schema expansion is required. Existing OHLCV and breadth history endpoints are sufficient.

## Config Impact

No new `config.py` values are required. This is a presentation and interaction upgrade.

## ADR Check

This design does not contradict existing ADRs. It does not change data sourcing, execution automation, or the EOD-first architecture.

## Testing Strategy

- Browser tests for scanner chart rendering, timeframe switching, and resize interaction
- Browser tests for market breadth chart rendering and resize interaction
- Build verification for frontend TypeScript integrity
- Focused API tests only if implementation reveals missing backend assumptions
