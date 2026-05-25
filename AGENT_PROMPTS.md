# Agent Prompts — Dhanustambha

Three ready-to-use prompts. Copy-paste these to start any coding session.

---

## PROMPT 1 — Getting Started / Resuming Work

Use this at the start of every new coding session.

```
You are a coding agent working on the Dhanustambha trading platform — a Python-based NSE momentum trading system.

MANDATORY ORIENTATION STEPS — do these before anything else:
1. Read README.md
2. Read AGENT_RULES.md
3. Read docs/architecture/ARCHITECTURE.md
4. Read docs/architecture/DECISIONS.md
5. Read docs/plans/PROGRESS.md
6. Read the current active plan in docs/plans/

After reading these files, tell me:
- What phase we are currently in
- What the last completed task was
- What the next task is
- Any open questions noted in PROGRESS.md

Then ask me: "Ready to proceed with [next task name]?"

Do NOT write any code until I confirm.
While checking the docs and design if you find any improvements can be done please suggest those.
```

---

## PROMPT 2 — Bug Fix / Investigation

Use this when something is broken and you need the agent to investigate and fix it.

```
You are a debugging agent working on the Dhanustambha trading platform.

MANDATORY FIRST STEPS:
1. Read AGENT_RULES.md (sections 1, 4, and 8 especially)
2. Read docs/architecture/ARCHITECTURE.md for context
3. Read the specific source file(s) relevant to the bug

THE BUG:
[Describe what is happening vs what should happen]
[Paste the full error message / stack trace here]
[Paste the command that triggered it]

YOUR DEBUGGING PROCESS:
1. State your hypothesis for the root cause
2. Show which file(s) and line(s) are involved
3. Write a failing test that reproduces the bug BEFORE fixing it
4. Implement the minimal fix
5. Confirm the test passes
6. Confirm no other tests broke: run `pytest tests/ -v`
7. Commit: `fix(scope): description of what was wrong and how it was fixed`
8. Update PROGRESS.md "Noted Issues" to mark the bug resolved

Do not change anything outside the scope of this bug fix.
```

Bug report:
- Where: website on page http://localhost:3000/trades 
- What happens: for open position charts are not correctly showing candles for the open position. attaching the screenshot of the issue. to describe the issue in words: for open position the chart is not showing the candles.
- What should happen: it should show the candles as per CMP. 

Before fixing:
1. Read the relevant file(s) in full — do not guess at their contents.
2. Read AGENT_RULES.md
3. Read docs/architecture/ARCHITECTURE.md for context
4. Identify the root cause before writing a single line of code. Tell me what it is.

Fix rules:
- Smallest possible change. One surgical str_replace, not a rewrite.
- Do not change unrelated code in the same file.
- After fixing, run: pytest tests/ -v to confirm no type errors introduced.
- If the fix requires a schema change, stop and ask me before proceeding.

Show me the exact before/after diff of what you changed.

---



## PROMPT 3 — Adding a New Feature

Use this when you want to extend the system with new functionality.

```
You are a feature-development agent working on the Dhanustambha trading platform.

MANDATORY FIRST STEPS:
1. Read README.md, AGENT_RULES.md, docs/architecture/ARCHITECTURE.md
2. Read docs/architecture/DECISIONS.md — understand past decisions before proposing new ones
3. Read docs/plans/PROGRESS.md — confirm Phase 1 is complete before building Phase 2+ features

THE FEATURE REQUEST:
[Describe the feature in plain language]
[Which layer does it belong to? (1=Data, 2=Monitor, 3=Scanner, 4=Trade, 5=Review)]

BEFORE WRITING ANY CODE, present:
1. Which files will be created or modified (follow the structure in README.md)
2. Any new config values needed in config.py
3. Any new DB tables or columns needed
4. Whether this feature contradicts any existing ADR in DECISIONS.md
5. The test plan (what tests will verify this works)

Wait for my approval of this plan before writing code.

After approval:
- Follow TDD: write tests first, then implement
- Commit after each logical unit of work
- Update docs/plans/PROGRESS.md when done
- If you make an architectural decision not covered by existing ADRs, add a new ADR to docs/architecture/DECISIONS.md
```


git remote add origin https://github.com/The-kadtan2027/Dhanustambha.git
https://github.com/The-kadtan2027/



Viewed main.py:1-193

Here is the blueprint for **Sub-Project 1: The Interactive Trade Book**. Let's review it piece by piece to make sure it aligns with your workflow.

### 1. The FastAPI Backend (Execute & Manage)
Currently, [src/api/main.py](cci:7://file:///d:/antigravity/Dhanustambha/src/api/main.py:0:0-0:0) is fully read-only. We will build three new state-changing endpoints:
* **`POST /trades/open`**: Accepts a ticker, setup type, entry price, stop price, and computed `shares`. It will call our core [open_trade()](cci:1://file:///d:/antigravity/Dhanustambha/src/trade/log.py:66:0-99:29) python logic to safely insert it into the SQLite DB.
* **`PUT /trades/update`**: Accepts a Trade ID and a new stop price, returning the updated open-trade state.
* **`PUT /trades/close`**: Accepts a Trade ID and an exit price, invoking [close_trade()](cci:1://file:///d:/antigravity/Dhanustambha/src/trade/log.py:102:0-151:5) moving it to the closed logs.

### 2. The Auto-Risk Position Sizer (Settings)
Since you chose Option A (Auto-Computed), the dashboard needs to know your total account size to safely apply your 1% risk maximum.
* We will add an **"Account Config"** input in the top header (or a settings sidebar) of the Next.js app.
* It will default to ₹500,000. When updated, it saves to your browser's local storage.
* When you open the trade modal, the exact number of shares and total allocation will instantly compute based on this saved Account Size and your specified Stop Loss.

### 3. The Watchlist Modal Flow (Frontend UI)
* Beside every ticker in the Daily Briefing table, we'll place an **"Execute" (⚡)** button.
* Clicking it opens a sleek, dark-mode overlay Modal.
* The Modal auto-fills the `Symbol` and `Setup Type` fields. 
* You manually type your `Entry Price` and `Stop Loss`. 
* The **Shares to Buy** and **Total Rs. At Risk** fields animate and compute dynamically beneath it.
* You click "Confirm Trade" which ships it to the backend `POST` endpoint, and closes the modal—your trade is officially live in the DB.

### 4. Trade Book Manager Page (Frontend UI)
* A new dedicated **Trade Book** page to replace [scripts/trade_manager.py](cci:7://file:///d:/antigravity/Dhanustambha/scripts/trade_manager.py:0:0-0:0).
* Shows all `OPEN` trades exactly as your terminal used to. 
* Next to each trade, inline input fields to update the Stop Loss (Action: `PUT update`) or record a Close (Action: `PUT close`).

Do these four design components sound good to you? Once you approve this, I will formally write up the Spec and we can kick off implementation!


You are a debugging agent working on the Dhanustambha trading platform.

MANDATORY FIRST STEPS:
1. Read AGENT_RULES.md (sections 1, 4, and 8 especially)
2. Read docs/architecture/ARCHITECTURE.md for context
3. Read the specific source file(s) relevant to the bug

THE BUG:
NFO:     127.0.0.1:64970 - "GET /ohlcv/GVT%26D?days=365 HTTP/1.1" 200 OK
INFO:     127.0.0.1:64970 - "GET /ohlcv/GLAND?days=90 HTTP/1.1" 200 OK
INFO:     127.0.0.1:51902 - "GET /market/prices?symbols=GLAND,BLS,GPIL,ENRIN,IGIL,GVT&D,ELGIEQUIP HTTP/1.1" 500 Internal Server Error
ERROR:    Exception in ASGI application
Traceback (most recent call last):
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\uvicorn\protocols\http\h11_impl.py", line 403, in run_asgi
    result = await app(  # type: ignore[func-returns-value]
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\uvicorn\middleware\proxy_headers.py", line 60, in __call__
    return await self.app(scope, receive, send)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\fastapi\applications.py", line 1054, in __call__
    await super().__call__(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\applications.py", line 113, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\middleware\errors.py", line 187, in __call__
    raise exc
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\middleware\errors.py", line 165, in __call__
    await self.app(scope, receive, _send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\middleware\cors.py", line 93, in __call__
    await self.simple_response(scope, receive, send, request_headers=headers)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\middleware\cors.py", line 144, in simple_response
    await self.app(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\middleware\exceptions.py", line 62, in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\routing.py", line 715, in __call__
    await self.middleware_stack(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\routing.py", line 735, in app
    await route.handle(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\routing.py", line 288, in handle
    await self.app(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\routing.py", line 76, in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\_exception_handler.py", line 53, in wrapped_app
    raise exc
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\_exception_handler.py", line 42, in wrapped_app
    await app(scope, receive, sender)
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\routing.py", line 73, in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\fastapi\routing.py", line 301, in app
    raw_response = await run_endpoint_function(
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\fastapi\routing.py", line 214, in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\starlette\concurrency.py", line 39, in run_in_threadpool
    return await anyio.to_thread.run_sync(func, *args)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\anyio\to_thread.py", line 63, in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\anyio\_backends\_asyncio.py", line 2518, in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
  File "C:\Users\gajuk\AppData\Roaming\Python\Python312\site-packages\anyio\_backends\_asyncio.py", line 1002, in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\antigravity\Dhanustambha\src\api\main.py", line 294, in market_prices
    prices = _price_cache.get_prices(sym_list)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\antigravity\Dhanustambha\src\api\main.py", line 76, in get_prices
    return {s: {**self.data[s], "is_cached": False} for s in symbols}
                  ~~~~~~~~~^^^
KeyError: 'GVT'

second issue is that user should be able to able to modify the computed shares to buy and stop loss in the trade modal. when user clicks on execute button in the watchlist table, it should open the trade modal and user should be able to modify the computed shares to buy and stop loss in the trade modal. and then click on confirm trade button to confirm the trade. deafult values can be computed values.

YOUR DEBUGGING PROCESS:
1. State your hypothesis for the root cause
2. Show which file(s) and line(s) are involved
3. Write a failing test that reproduces the bug BEFORE fixing it
4. Implement the minimal fix
5. Confirm the test passes
6. Confirm no other tests broke: run `pytest tests/ -v`
7. Commit: `fix(scope): description of what was wrong and how it was fixed`
8. Update PROGRESS.md "Noted Issues" to mark the bug resolved

Do not change anything outside the scope of this bug fix.