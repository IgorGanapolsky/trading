# Data Integrity Rules

## Authority by Question

There is no single JSON file that is authoritative for every question:

```text
Alpaca API
  ├─ account / positions / orders ─> data/system_state.json (broker snapshot)
  ├─ paired completed structures ──> data/trades.json.trades (outcome rows)
  └─ unmatched fills / cash ───────> reconciliation diagnostics only

data/trades.json.trades
  └─ src/analytics/trade_evidence.py
       ├─ row-derived edge metrics
       ├─ active-strategy ML dataset
       └─ verified RAG trade documents
```

## Key Facts

- Alpaca is the source of truth for current broker state.
- `data/trades.json.trades` is the paired closed-structure outcome ledger.
- `data/trades.json.stats` is a derived cache and must reconcile to physical rows.
- Unmatched orders are never trades. Their cash stays in `unpaired_*`
  reconciliation fields and is excluded from sample size, win rate, expectancy,
  profit factor, ML labels, and RAG outcome documents.
- `data/trades_*.json` and `options_trades_*.json` are raw/deprecated execution
  telemetry. They must never be promoted directly into the paired ledger.
- Active-strategy learning is strategy-scoped and protocol-validated. Killed
  strategy rows cannot train the successor model.
- Cloud Run has no local files — webhook readers fetch the published evidence
  packet or canonical ledgers from GitHub.

## Files

| File                                    | Purpose                                      | Writer                         |
| --------------------------------------- | -------------------------------------------- | ------------------------------ |
| `data/system_state.json`                | Broker account, positions, orders, raw fills | broker sync workflows          |
| `data/trades.json`                      | Paired closed-structure outcomes             | closed-position synchronizer   |
| `data/put_credit_entries.json`          | Active put-credit lifecycle journal          | `spy_put_credit.py`            |
| `data/rag/verified_trade_evidence.json` | Generated verified RAG packet                | `sync_trades_to_rag.py`        |
| `data/trades_*.json`                    | **DEPRECATED raw telemetry**                 | Never use for edge or learning |

## Monitoring

- `scripts/system_health_check.py` and `scripts/self_healing_check.py` fail when
  reported stats mix paired structures with unmatched orders.
- `src/analytics/trade_evidence.py` publishes a deterministic dataset hash,
  rejection counts, protocol violations, and row-derived metrics.
- Zero verified active-strategy outcomes means no ML training and no profit claim.

## Credentials

- NEVER hardcode credentials (GitGuardian incident Feb 3, 2026)
- All code uses `get_alpaca_credentials()` from `src/utils/alpaca_client.py`
- No default values in `os.environ.get()` for secrets
