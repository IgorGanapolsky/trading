# Live Strategy Spec

This document describes the current validated playbook surface, not a promise of current profitability.

## Baseline Playbook

- Underlying: `SPY`
- Structure family: defined-risk options premium structures
- Primary template: iron-condor style entries when gates allow them
- Target DTE band: `30-45`
- Typical short-strike selection: around `15 delta`
- Position sizing: weekly gate controlled, currently capped by risk mode

## What Is Live Right Now

Current operating truth should be pulled from the canonical ledgers and public dashboard:

- [Public status bundle](data/public_status.json)
- [Operator dashboard](rag-query.html)
- [System state](../data/system_state.json)
- [Paired-trade ledger](../data/trades.json)

## Operating Rules

- No scale-up while the weekly gate blocks new positions.
- No marketing claims based on stale snapshots.
- Completed paired-trade evidence matters more than fill activity.
- Public copy must stay congruent with broker-backed status and canonical ledgers.
