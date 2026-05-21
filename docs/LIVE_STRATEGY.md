# Live Strategy Spec

This document describes the current playbook surface. It is not a validated edge and not a promise of profitability — see [`docs/research/2026-05-19-edge-analysis.md`](research/2026-05-19-edge-analysis.md).

## Baseline Playbook

- Underlying: `SPY`
- Structure family: defined-risk options premium structures
- Primary template: iron-condor style entries
- **Entry Window**: one structure per day maximum. Entries are **not** pre-conditioned on day-of-week — the "Thursday ~60%" slice failed multiple-comparison correction (Bonferroni adj_p = 0.190) and is not a validated edge. During the validation cohort, **Tuesday entries are avoided** (the only descriptively data-supported filter: Tuesday n=17 won 1, expectancy −$170.65).
- **Entry Buffer**: Minimum `14 DTE` required for all new positions.
- **Exit Discipline**:
  - Profit Target: `15%` to `20%` of credit received (May 2026 Defensive Regime).
  - Stop Loss: `100%` of credit received.
  - **Time Exit**: Mandatory close at `7 DTE` (Lesson LL-268) to eliminate gamma risk.
- Typical short-strike selection: `20 delta` (Widened to 20-point wings for May/June 2026)

## What Is Live Right Now

Current operating truth should be pulled from the canonical ledgers and public dashboard:

- [Public status bundle](data/public_status.json)
- [Operator dashboard](https://github.com/IgorGanapolsky/trading/wiki/Progress-Dashboard)
- [System state](../data/system_state.json)
- [Paired-trade ledger](../data/trades.json)

## Operating Rules

- No scale-up while the weekly gate blocks new positions.
- No marketing claims based on stale snapshots.
- Completed paired-trade evidence matters more than fill activity.
- Public copy must stay congruent with broker-backed status and canonical ledgers.
