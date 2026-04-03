# Development Engine and Evidence

Generated from canonical ledgers at `2026-04-03T11:03:57.882537-04:00`.

This page explains how public-facing system copy stays congruent with live state.

## Evidence Surfaces

- `artifacts/daily_scorecard/latest_daily_scorecard.json` for broker-backed daily status
- `data/system_state.json` for active gate state
- `data/trades.json` for paired-trade ledger stats
- `docs/data/public_status.json` for public pages and wiki rendering

## Current Public-Copy Rules

- No frozen portfolio numbers in README, About, or wiki prose
- Public pages render from generated status data or link to canonical live surfaces
- Repo metadata and wiki must match the generated public status bundle

## Current Operator Summary

- Paper equity: `$93,990.30`
- Total realized P/L ledger: `$-3,402.00`
- Weekly gate mode: `validation`
- Block new positions: `False`

## Exact Blocker

`Insufficient recent weekly evidence; keep conservative sizing. Cadence KPI miss: setups 0/1, closed trades 1/1.`
