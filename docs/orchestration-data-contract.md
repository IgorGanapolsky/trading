# Orchestration Data Contract

## Authoritative Files

- `data/system_state.json`: canonical account/position/trade snapshot
- `data/trades.json`: master trade ledger for win-rate/stat analytics
- `data/trades_*.json`: legacy compatibility inputs only
- `data/runtime/*`: runtime telemetry and short-lived artifacts

## Writer Ownership

- `scripts/sync_alpaca_state.py`
  - writes: `data/system_state.json`, runtime sync artifacts
- `scripts/sync_trades_to_rag.py`
  - writes: `data/trades.json`, `data/trades_backup.json`
- Trading workflows (`daily-trading`, `iron-condor-*`)
  - append session/order artifacts under `data/` without replacing canonical broker sync output

## Reader Ownership

- Orchestrator/runtime guards:
  - read `data/system_state.json` first
- Webhook/query paths:
  - system-state-first, legacy fallback only when required
- Analytics/reporting:
  - consume `data/trades.json` for longitudinal metrics

## Conflict Resolution Order

1. `data/system_state.json` (broker-sync truth)
2. `data/trades.json` (ledger truth for analytics)
3. `data/trades_*.json` (legacy fallback only)

If two sources disagree, prefer higher priority source and trigger a sync/reconciliation run.
