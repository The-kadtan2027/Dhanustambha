# Backend Risk Quote Trade Ticket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GUI trade execution production-grade by moving position sizing and validation from the browser into the backend API.

**Architecture:** Add a backend quote endpoint that wraps `src.trade.sizer.calculate_position_size()` and exposes validation details to the frontend. Update trade opening to require an account size and server-calculated share count, then update the dashboard trade ticket to request and display the backend quote before allowing confirmation.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js, React, TypeScript.

---

## File Map

- Modify `src/api/main.py`: add trade quote request/response models, `POST /trades/quote`, and server-side validation in `POST /trades/open`.
- Modify `tests/test_api.py`: add API tests for valid quotes, invalid stops, defensive sizing, and open-trade share enforcement.
- Modify `frontend/app/dashboard-client.tsx`: replace local share math with backend quote state and validation messaging.

## Task 1: Backend Trade Quote Contract

- [x] Add failing tests in `tests/test_api.py` for:
  - `POST /trades/quote` returns shares, risk amount, position value, risk percent, and market verdict.
  - invalid stop price returns HTTP 422 with a clear validation message.
  - defensive breadth verdict halves sizing.
- [x] Run the focused tests and verify they fail because `/trades/quote` does not exist.
- [x] Implement `TradeQuoteRequest`, `_build_trade_quote()`, and `POST /trades/quote` in `src/api/main.py`.
- [x] Run the focused tests and verify they pass.

## Task 2: Server-Side Open Trade Enforcement

- [x] Add a failing test that opens a trade with `account_size`, `entry_price`, and `stop_price`, but a deliberately wrong `shares` value; the API must store the server-calculated share count instead.
- [x] Add a failing test that invalid stop/entry combinations are rejected by `POST /trades/open`.
- [x] Update `TradeOpenRequest` to accept `account_size`.
- [x] Update `api_open_trade()` to call the same quote builder and pass validated shares to `open_trade()`.
- [x] Run `tests/test_api.py` and verify all tests pass.

## Task 3: Dashboard Trade Ticket Uses Backend Quote

- [x] Update `CandidateDetailPanel` to fetch `/trades/quote` when account size, selected candidate, or stop price changes.
- [x] Display backend quote fields: shares, risk amount, position value, R unit, and market verdict.
- [x] Disable confirmation until the backend quote is valid.
- [x] Submit `account_size` to `/trades/open` and stop sending browser-calculated `shares` as the source of truth.
- [x] Run `cmd /c npm run build`.

## Task 4: Verification

- [x] Run `C:\Program Files\Python312\python.exe -m pytest tests\test_api.py -v`.
- [x] Run `cmd /c npm run build` in `frontend`.
- [x] Run a browser smoke test against production mode that opens a candidate, enters a stop, receives a backend quote, and cancels before opening a trade.
