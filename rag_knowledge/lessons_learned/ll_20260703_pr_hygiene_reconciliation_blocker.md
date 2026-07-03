# LL-20260703: PR Hygiene Merged Cleanly, Reconciliation Still Blocks Trading

**Date**: 2026-07-03
**Severity**: HIGH
**Scope**: PR management, branch hygiene, CI verification, trading readiness

## Summary

PR merge readiness can be green while operational trading readiness remains blocked.
On 2026-07-03, PRs #4179, #4180, #4177, and #4181 were merged and orphan
remote branches were cleaned, but the post-merge broker-vs-paired reconciliation
workflow still failed on live data after the import-path fix. Do not treat this
state as "system hygiene complete" or "safe to trade faster" until the
reconciliation alert and ML/RAG trading gate both pass.

## Evidence

- PR #4179 merged with commit `34c2a2e5cb9b9bc50785070aca76e6e05edab307`.
- PR #4180 merged with commit `5083a2e996105bdb87837679f8ca794c98f7eca2`.
- PR #4177 merged with commit `d4666346f814ec40c2e351bd2cfe0cb8eee81297`.
- PR #4181 merged with commit `4445162ab284748e52aef9cb6214dd41df124f36`.
- PR #4181 fixed direct script execution for `scripts/sync_closed_positions.py`
  by inserting the repo root into `sys.path` before importing `src.*` modules.
- Manual reconciliation run `28685200443` proved the import fix worked:
  `Fetched 163 closed trades from PAPER history` and
  `Updated trades.json: new_closed=0 normalized_ids=0 closed_total=179`.
- The same reconciliation run still failed with a real ledger alert:
  `broker=$-1420.00 paired_in=$-3755.00 paired_out=$-3498.00 delta=$2335.00
  threshold=$150.00`.
- Latest report on `origin/main` commit `c6b9498fabd0aaeef59556d255f3c5b351724b5a`
  recorded `alert_fired=true`, `paired_unpaired_order_count=15`, and
  `delta_dollars=2335.0`.
- Deep research ML/RAG dry run blocked trading with win rate `16.8%`, expectancy
  `$-32.21/trade`, and profit factor `0.70`.

## Lesson

For future PR hygiene sessions:

1. Merge-ready PRs are not enough for trading readiness.
2. A reconciliation failure after the sync path is fixed is a data/trading
   blocker, not a CI nuisance.
3. Keep trading blocked when the ML/RAG gate reports negative expectancy or
   profit factor below 1.0, even if code checks are green.
4. Preserve dirty local worktrees and document them instead of deleting them.
5. If an automation branch has no PR and only generated self-heal state, delete
   it after its source workflow completes and re-fetch to confirm only
   `origin/main` remains.

## Next Actions

- Investigate the 15 unpaired order records driving the reconciliation delta.
- Re-run the reconciliation workflow after the ledger gap is fixed.
- Re-run the deep research ML/RAG gate and keep trade execution blocked until
  expectancy is positive, win rate is at least 50%, and profit factor is above
  1.0.
