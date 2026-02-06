# Data Integrity Rules

## Single Source of Truth

**CANONICAL**: `data/system_state.json → trade_history`

```text
Alpaca API → sync-system-state.yml → system_state.json
                                           ↑
                  trade_sync.py ───────────┘
                                           ↓
              Dialogflow Webhook ← GitHub API fetch
```

## Key Facts

- Cloud Run has no local files — webhook fetches from GitHub API
- Alpaca is source of truth — workflow syncs real broker data
- `data/trades_*.json` = **DEPRECATED** (LL-230)

## Files

| File                     | Purpose                  | Writer                               |
| ------------------------ | ------------------------ | ------------------------------------ |
| `data/system_state.json` | **CANONICAL** trade data | sync-system-state.yml, trade_sync.py |
| `data/trades_*.json`     | **DEPRECATED**           | Legacy — do not use                  |

## Monitoring

- CI workflow `webhook-integration-test.yml` validates `trades_loaded > 0`
- Failure = data source mismatch (see LL-230)

## Credentials

- NEVER hardcode credentials (GitGuardian incident Feb 3, 2026)
- All code uses `get_alpaca_credentials()` from `src/utils/alpaca_client.py`
- No default values in `os.environ.get()` for secrets
