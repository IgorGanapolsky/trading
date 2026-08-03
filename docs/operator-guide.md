# Operator guide

Short human runbook. Agents should also load [`skills/trading-ops/SKILL.md`](../skills/trading-ops/SKILL.md).

## What is live today

| Item           | Value                    |
| -------------- | ------------------------ |
| Active family  | `spy_put_credit` (paper) |
| Live capital   | Blocked                  |
| IC new entries | Killed                   |
| Residual IC    | Exit/manage only         |

Source: `data/runtime/strategy_kill_switch.json`.

## Daily loop

```bash
# 1. Broker truth
python scripts/sync_alpaca_state.py
python scripts/sync_closed_positions.py

# 2. Hygiene
python scripts/audit_open_inventory.py   # must be clean for new risk
python scripts/system_health_check.py

# 3. Strategy status / plan
python scripts/spy_put_credit.py --status
python scripts/spy_put_credit.py --dry-run
```

## Truth sources

| Question                | File                             |
| ----------------------- | -------------------------------- |
| Equity / positions      | `data/system_state.json`         |
| Closed structure P/L    | `data/trades.json`               |
| Open put-credit journal | `data/put_credit_entries.json`   |
| Lessons                 | `rag_knowledge/lessons_learned/` |

## Hard rules

1. Paper validation only until n≥30 put-credit cohort with expectancy > 0 and PF > 1.
2. Do not freehand-close options outside `spy_put_credit.py` or `residual_ic_manager.py`.
3. Do not clear halt files to force trading.
4. Do not re-enable IC entry workflows.

## Tests before merge

```bash
make check
make dry-run
```

## When something fails

1. Read the failing command output.
2. Query RAG lessons for the error pattern.
3. Fix with a test when possible.
4. Log a lesson if severity ≥ 4 or the mistake already happened once.
