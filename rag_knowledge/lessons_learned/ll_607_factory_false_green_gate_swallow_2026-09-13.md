# LL-607 Paper factory false-green: GATE BLOCKED swallowed as skip

## Context

2026-09-13. Operator asked if the system is making real money. Live equity is $0.
Paired put-credit n=3. Friday 2026-09-11 Put Credit Validation (runs 34614102162
and 34625574050) found a valid 1-lot SPY opportunity then:

`MANDATORY GATE BLOCKED: Trade blocked by stale context: context_engine_index`

The job still concluded **success** because `.github/workflows/put-credit-validation.yml`
wrapped `--execute-paper` in `|| { echo skipped; true }`.

AGENT-604 (#4607) skips that stale-index freeze for controlled 1-lot paper
spy_put_credit, but it merged Saturday after the session. The swallow would
hide the next distinct gate miss the same way.

## Prevention

- `--execute-paper` returns 3 on MANDATORY GATE BLOCKED / GATE ERROR
  (`MandatoryGateSubmitError`). Workflow fails closed on rc 3.
- Scheduled entry slots run `scripts/check_entry_cadence.py` after the attempt.
- Do not treat "workflow green" as "cohort grew".

## Do not

- Flip `live_blocked` or deposit live cash
- Count journal-only `broker_reconcile_flat` rows as paired edge
- Revive iron-condor entries
