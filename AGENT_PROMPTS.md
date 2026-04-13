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
