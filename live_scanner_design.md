# Design: Somewhat Live Market Scanner (Stream I)

## Objective
Enable running the [daily_briefing.py](file:///D:/antigravity/Dhanustambha/tests/test_daily_briefing.py) pipeline (Breadth Monitor + Setup Scanners) during market hours by fetching live OHLCV data via scrapers/APIs, rather than waiting for the EOD Bhavcopy.

## Proposed Architecture

### 1. Enhanced Scraper ([src/ingestion/fetcher.py](file:///D:/antigravity/Dhanustambha/src/ingestion/fetcher.py))
Modify [_scrape_google_finance](file:///D:/antigravity/Dhanustambha/src/ingestion/fetcher.py#29-68) and [fetch_live_prices](file:///D:/antigravity/Dhanustambha/src/ingestion/fetcher.py#70-139) to return full OHLCV objects instead of just a single price.
- **Goal:** Extract [open](file:///D:/antigravity/Dhanustambha/src/trade/log.py#67-101), `high`, [low](file:///D:/antigravity/Dhanustambha/tests/test_api.py#225-237), [close](file:///D:/antigravity/Dhanustambha/src/trade/log.py#103-153), and `volume` from the Google Finance page source.
- **Challenge:** Google Finance displays Low/High as a range (e.g., "1,320.00 - 1,350.00"). Need regex to split this.
- **Volume:** Often displayed as "1.2M". Need a converter to absolute integers.

### 2. Live Ingestion Layer ([src/ingestion/store.py](file:///d:/antigravity/Dhanustambha/src/ingestion/store.py))
Create a "Transient" or "Shadow" record in the [ohlcv](file:///D:/antigravity/Dhanustambha/src/api/main.py#386-413) table for the current date.
- **Mechanism:** `upsert_live_ohlcv(symbol, data)`
- **Safety:** Use a special flag or handle the [date](file:///D:/antigravity/Dhanustambha/src/api/main.py#291-299) logic so that the live data is replaced by the official NSE Bhavcopy once it becomes available at 16:30 IST.

### 3. API Integration ([src/api/main.py](file:///D:/antigravity/Dhanustambha/src/api/main.py))
Add a `POST /briefing/live` endpoint.
- **Logic:**
  1. Fetch live OHLCV for all symbols in the `NIFTY500`.
  2. Inject/Upsert into the DB for `today`.
  3. Run `compute_breadth()` and `run_scanners()` for `today`.
  4. Return the resulting watchlist.

### 4. Frontend: "Live Scan" Button
Add a "Run Live Scan 🚀" button on the Scanners page.
- **UX:** Show a "Live" badge on candidates found during market hours to distinguish them from finalized EOD candidates.

## Implementation Steps

### Phase 1: Data Extraction
- Update [fetch_live_prices](file:///D:/antigravity/Dhanustambha/src/ingestion/fetcher.py#70-139) to `fetch_live_session_data` returning `{ symbol: {o, h, l, c, v} }`.
- Implement unit tests for the regex parsers (handling "1.2M" volume and range strings).

### Phase 2: Pipeline Adaptation
- Modify breadth and scanner logic to correctly interpret "today" even if the market hasn't closed (e.g., handles the fact that "today's close" = LTP).

### Phase 3: UI Trigger
- Connect the frontend button to the new `/briefing/live` endpoint.

---

> [!IMPORTANT]
> **Performance Caveat:** Scraping 500 symbols sequentially is slow (~5-10 mins). 
> **Solution:** Use `ThreadPoolExecutor` (already in [fetcher.py](file:///D:/antigravity/Dhanustambha/tests/test_fetcher.py)) to parallelize the scraper calls.

> [!WARNING]
> **Data Quality:** Scraped intra-day volume and ranges may slightly differ from finalized EOD data. Results should be treated as "pre-market-close alerts."
