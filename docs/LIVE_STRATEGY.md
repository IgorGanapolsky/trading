# Live Strategy Spec

This document describes the current validated playbook surface, not a promise of current profitability.

## Baseline Playbook

- Underlying: `SPY`
- Structure family: defined-risk options premium structures
- Primary template: iron-condor style entries
- **Entry Window**: any weekday (Thursday-only gate retired 2026-05-20 — the "60% Thursday" claim did not survive Bonferroni correction at α=0.05; see `docs/research/2026-05-19-edge-analysis.md`).
- **Entry Buffer**: Minimum `14 DTE` required for all new positions.
- **Exit Discipline**:
  - Profit Target: `15%` to `20%` of credit received (May 2026 Defensive Regime).
  - Stop Loss: `100%` of credit received.
  - **Time Exit**: Mandatory close at `7 DTE` (Lesson LL-268) to eliminate gamma risk.
- Typical short-strike selection: `20 delta` (Widened to 20-point wings for May/June 2026)

## What Is Live Right Now

Current operating truth should be pulled from the canonical ledgers and public dashboard:

- [System state](../data/system_state.json)
- [Paired-trade ledger](../data/trades.json)

## Operating Rules

- No scale-up while the weekly gate blocks new positions.
- No marketing claims based on stale snapshots.
- Completed paired-trade evidence matters more than fill activity.
- Public copy must stay congruent with broker-backed status and canonical ledgers.
