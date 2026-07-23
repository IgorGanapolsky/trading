---
milestone: "v2.0-put-credit-edge"
current_phase: 1
status: "executing"
---

# Project State — Put Credit Edge OS

Last activity: 2026-07-23 — GSD roadmap reset to put-credit validation; cohort scorecard + Ralph tick

### Current Phase

Phase 1: Cohort Truth Loop

### Active strategy

- Family: `spy_put_credit` only
- Paper-only; live_blocked
- Profile: 1-lot, max_daily=3, max_concurrent=2, min_credit=$0.50

### Reality (do not inflate)

- Closed put-credit cohort: **0** (all `trades.json` rows still iron_condor)
- 1 open PCS holding (min 24h not met)
- Residual ICs exit-only
- Profitability: **unproven**

### Blockers

- Need closed put-credit sample n≥30 before edge judgment
- Live capital blocked by design

### Ralph loop

- Tick: `scripts/ralph_gsd_profit_tick.sh`
- State: `.claude/ralph/state.json`
