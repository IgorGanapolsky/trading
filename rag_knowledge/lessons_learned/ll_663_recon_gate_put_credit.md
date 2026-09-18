# LL-663 — Daily recon must gate on spy_put_credit, not killed IC 50-lot noise

**Date:** 2026-09-18
**Severity:** 4
**Issue:** AGENT-663
**Evidence:** Daily Broker-vs-Paired Reconciliation failed 5 weekdays (Sep 14–18).
Run 35395684281: `broker_realized=16`, `paired_in=-1231`, `delta=1247`.

## Mistake

Treating all-family broker vs paired as the weekday fail gate after IC Simple was
killed. `trade_history` still holds 34 incomplete 50-lot SIMPLE+MLEG groups whose
cash coincidentally nets near $0 (today +$16). Paired `trades.json` still has
iron_condor n=161 / -$7662 plus unpaired $2130. The $150 threshold then fails
every weekday even though the active paper family is spy_put_credit.

Raising `THRESHOLD_DOLLARS` would hide a real ledger gap. Ignoring the job
would hide a real put-credit mismatch later.

## Fix

`--gate-family spy_put_credit` (daily workflow): broker = complete 2-leg SPY put
MLEG groups (net qty 0); paired = `strategy=spy_put_credit` closed rows only.
Do not fold unpaired IC cash or underconsumed 50-lot fills into that gate.
Keep all-family delta / incomplete-group counts on the JSON as diagnostics.

Default `--gate-family all` preserves existing unit tests and LL-354 behavior.

## Verify

`pytest tests/unit/test_reconciliation.py` plus local
`scripts/reconcile_broker_vs_paired.py --gate-family spy_put_credit`.
