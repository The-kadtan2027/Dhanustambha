# EP Deepening Playbook Design

## Objective
Tighten the Episodic Pivot (EP) execution into a near-systematic playbook. This closes the gap between raw scanner signals and actual trade execution by defining explicit rules for entry limits, skip conditions, and tiered exits.

## 1. Architecture Overview
The EP Deepening spec adds one new module and extends existing downstream systems without altering the core detection scanner logic.

*   `src/scanner/episodic_pivot.py`: REMAINS UNCHANGED.
*   **[NEW] `src/review/ep_playbook.py`**: A new top-level engine that processes EP signals from the scanner.
    *   Evaluates entry rules (price + market gate).
    *   Applies tiered exit rules (trailing stop evaluation).
    *   Outputs a daily action card per symbol (`ENTER`, `SKIP`, `HOLD`, `TRAIL`).
*   **[MODIFIED] `scripts/daily_briefing.py`**: Integrates `ep_playbook` to show entry limits, stop losses, and instructions alongside the EP candidates.
*   **[MODIFIED] `src/execution/trade_manager.py`**: Open EP trades will now store an `EP_TIER` (A+ or B) and a `trailing_stop_price`, updating daily based on instructions from `ep_playbook.py`.

## 2. Research Component (Data Validation First)
Before hardcoding the trail widths, we will write a script to validate them against historical Maximum Forward Excursion (MFE) data.
*   **Script**: `scripts/research_ep_exit_rules.py`
*   **Input**: Existing calibration CSVs `data/calibration/*-episodic_pivot-NIFTY500-signals.csv`.
*   **Action**: Simulates various trailing stop widths (e.g., 8%, 12%) for tier A+ and tier B signals against the MFE data to find the optimal width that captures the highest R-multiple without premature stop-out.
*   **Output**: Promotes validated percentages into `config.py` as `EP_TRAIL_A_PCT` and `EP_TRAIL_B_PCT`.

## 3. Entry Rules (Next-Morning, EOD-Friendly)
Two critical conditions must both pass before a new entry is approved.

1.  **Price Gate**: `current_price <= gap_open_price * (1 + EP_ENTRY_MAX_CHASE_PCT)` (default 5%).
    *   If the price runs too far beyond the gap open, we do not chase. Tag: `CHASED — SKIP`.
2.  **Market Gate**: `market_verdict in ["OFFENSIVE", "DEFENSIVE"]`.
    *   If the market is `AVOID`, no entry is made. Tag: `MARKET WEAK — SKIP`.

**Fail Gate**: If `current_price < gap_open_price`, the gap failed intraday. Tag: `GAP FAILED — SKIP`.

## 4. Exit Rules (Tiered Trailing Stops)
Exits follow a tiered, trailing framework to allow winners to run while cutting standard setups faster. Once a trailing trigger is hit, the stop trails from the rolling high. The stop has a **breakeven floor** and only moves up.

| Tier | Trail Width | Activation | Update Frequency | Time Backstop |
|---|---|---|---|---|
| **A+** | 12% (subject to research) | Start trailing at `+5%` gain | Daily (EOD) | 30 trading days max |
| **B** | 8% (subject to research) | Start trailing at `+3%` gain | Daily (EOD) | 20 trading days max |

## 5. Daily Workflow Data Flow
1.  **After-market**: Scanner finds EP candidates.
2.  `ep_playbook.evaluate_entries()` processes the candidates and outputs explicit actions.
3.  `daily_briefing.py` prints the action card to the user:
    *   `RAILTEL EP-A+ gap_open=185.0 entry_limit=194.3 verdict=OFFENSIVE ✅ ENTER`
    *   `DIXON EP-B gap_open=420.0 entry_limit=441.0 verdict=AVOID ⛔ SKIP (market)`
4.  `ep_playbook.evaluate_open_trades()` evaluates existing stored EP trades in `trade_manager.py` and output a daily update:
    *   Update `trailing_stop_price`
    *   Issue a `TRAIL TO X` or `EXIT NOW` action.
