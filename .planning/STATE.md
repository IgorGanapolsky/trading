---
milestone: "v2.0-put-credit-edge"
current_phase: 2
status: "executing"
framework: "ralph+gsd"
updated: "2026-07-24"
---

# Project State — Put Credit Edge OS (Ralph + GSD)

Last activity: 2026-07-24 — Phase 1 complete on main; Phase 2 entry quality shipping

## Current Phase

**Phase 2: Smart Entry Quality** (executing)

Phase 1 (Cohort Truth Loop) — DONE on main:

- Cohort scorecard family-isolated
- Inventory + manage-exits + residual IC on every Ralph tick
- Regime gate + entry logging + exit counterfactuals + rolling-20

## Active strategy

- Family: `spy_put_credit` only
- Paper-only; live_blocked=true
- Profile: 1-lot, max_daily=3, max_concurrent=2, min_credit=$0.50
- Regime hard gate: IVR>=30, VIX<=30 (soft: SPY 200-DMA)

## Reality (do not inflate)

- Closed put-credit cohort: **0** → INSUFFICIENT_SAMPLE
- Open PCS: **2** (hold)
- Residual IC: exit-only hold
- Profitability: **unproven**
- Live deposit ready: **false**

## Blockers

- Need closed put-credit sample n>=30 before edge judgment
- Live capital blocked by design
- Hard RAG PR #4281 — land when green

## Ralph loop

- Tick: `scripts/ralph_gsd_profit_tick.sh` / `.py`
- State: `.claude/ralph/state.json`
- Goal: `put_credit_edge_proof_n30`
- Completion promise: `EDGE_GATE_READY_OR_KILLED`
- Tick schema: `ralph-gsd-profit-tick/2` (includes regime)

## GSD next

1. Land #4281 (hard RAG / no ML theater)
2. Keep ticks green; manage exits when TP/stop
3. Advance closed n toward 30 under regime gate
4. Phase 4 decision only at n=30
