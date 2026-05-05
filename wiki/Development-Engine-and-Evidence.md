# Development Engine and Evidence

Generated from canonical ledgers at `2026-05-05T15:09:33.509927+00:00`.

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

- Paper equity: `$93,519.70`
- Total realized P/L ledger: `$-3,669.00`
- Weekly gate mode: `validation_reset`
- Block new positions: `False`

## Exact Blocker

`Negative lifetime expectancy freezes North Star claims; only minimum-size paper validation is allowed because a valid changed-rule hypothesis is present.`
