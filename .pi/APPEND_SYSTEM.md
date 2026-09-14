# Trading lab — Pi append (do not replace Pi's default system prompt)

This checkout is the **paper** SPY put-credit lab. Pi is a harness, not a broker.

## Hard constraints

- Active family: `spy_put_credit`. Iron-condor **new entries killed**.
- Paper only. `data/runtime/strategy_kill_switch.json` has `live_blocked: true`.
- Do not submit live orders. Do not freehand-close positions.
- Do not delete `data/TRADING_HALTED` / `data/SYSTEM_HALTED`.
- Do not edit `IRON_CONDOR_STOP_LOSS_MULTIPLIER`, `NORTH_STAR_MONTHLY_AFTER_TAX`, or `FORBIDDEN_STRATEGIES`.
- Do not `pi install` third-party MCP packages. Pi core has **no MCP**; this repo uses CLI skills. Grok/Claude already have Linear/GitHub MCP.

## Operator path

Prefer deterministic scripts over model guesses:

```bash
.venv/bin/python scripts/spy_put_credit.py --status
.venv/bin/python scripts/spy_put_credit.py --dry-run
.venv/bin/python scripts/put_credit_cohort_scorecard.py --json
.venv/bin/python scripts/audit_open_inventory.py
```

If `scripts/pi_trading_bridge.py` exists (PR #4624), use it for `/status` `/dryrun` `/exits` `/scorecard`.

0 paired put-credit closes is not edge. Do not claim profit or deposit live cash until kill verdict is `EDGE_CANDIDATE` (n≥30, expectancy>0, PF>1, total PnL>0).
