---
name: pi-paper-factory
description: >
  Run the paper SPY put-credit factory from Pi (pi.dev). Status, dry-run, exits,
  scorecard. No live, no MCP install, no iron-condor entries.
---

# Pi paper factory

Pi is a **harness**. This skill is the connector. Do not `pi install` npm MCP adapters.

## When

User is in this repo and asks status, dry-run, exits, cohort, or "use Pi".

## Commands (deterministic)

```bash
.venv/bin/python scripts/spy_put_credit.py --status
.venv/bin/python scripts/spy_put_credit.py --dry-run
.venv/bin/python scripts/spy_put_credit.py --manage-exits --dry-run
.venv/bin/python scripts/put_credit_cohort_scorecard.py --json
.venv/bin/python scripts/audit_open_inventory.py
```

If `scripts/pi_trading_bridge.py` is on the branch (PR #4624):

```bash
.venv/bin/python scripts/pi_trading_bridge.py status --json
.venv/bin/python scripts/pi_trading_bridge.py dry-run --json
.venv/bin/python scripts/pi_trading_bridge.py scorecard --json
```

Print-mode (no TUI): `pi -p --no-tools "summarize the scorecard JSON"` only after the JSON exists. Do not spend cloud tokens to _plan_ a trade the script already planned.

## Never

- Live orders / `--live`
- Close positions outside `--manage-exits` / residual IC manager
- Delete halt files
- Claim EDGE_CANDIDATE before n≥30
- Install `pi-mcp-adapter` or other unreviewed Pi MCP packages into this project
