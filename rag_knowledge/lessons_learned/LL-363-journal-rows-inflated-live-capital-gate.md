# LL-363: Entry-Journal Rows Inflated the Sample Size Gating Live Capital

**Date**: August 3, 2026
**Category**: Data Integrity / Risk / Graph RAG
**Severity**: CRITICAL
**Related**: LL-361, LL-362, data-integrity.md, kill-criteria.md

## Summary

The temporal trade graph counted rows from `data/put_credit_entries.json` — the **entry
lifecycle journal** — as closed trades. One of them was still `exit_pending`. Neither
carries `realized_pnl`, so both defaulted to zero and were classified as breakeven.

Effect on the active strategy family:

| Metric          | Reported | Truth (paired ledger) |
| --------------- | -------- | --------------------- |
| Sample size `n` | 3        | **1**                 |
| Expectancy      | 5.67     | **17.00**             |
| Scorable total  | 164      | **162**               |

## Why this was the most dangerous defect of the session

`src/bank/live_gate.py` gates real capital on `EDGE_N_MIN = 30` against this exact
sample count. The bug moved the reported number **toward** the threshold. An error that
overstates progress toward deploying money is categorically worse than one that
understates it — the failure mode is funding an unproven approach, not delaying a proven
one.

`data-integrity.md` already said this plainly:

> Unmatched orders are never trades. Their cash stays in the unpaired reconciliation
> fields and is excluded from sample size, win rate, expectancy, profit factor, ML
> labels, and RAG outcome documents.

The rule existed; the new code simply did not honor it.

## Root Cause

`build.py` reused one node-construction path for both sources and tagged neither, so
downstream aggregation had no way to tell a broker-reconciled close from an open entry.
Convenience at ingestion became a correctness hole at the metric.

## Fix

1. Every trade node carries `evidence_tier`: `paired_ledger` or `journal`.
2. `policy_cohorts()` and `loss_attribution()` score **only** `paired_ledger`.
3. Journal rows stay in the graph for lifecycle traversal but are counted nowhere.
4. `loss_attribution()` returns `excluded_non_scorable` so the exclusion is visible
   rather than silent — a table that quietly drops rows reads as complete when it is not.

## Prevention

- `test_journal_rows_never_enter_metrics` — asserts n stays 1, not 3, and that
  exclusions are reported.
- `test_policy_cohorts_exclude_journal_rows` — a journal row cannot form a cohort.

## Rule

**When a number feeds a capital gate, its provenance is part of its definition.** A count
is not "trades" — it is "broker-reconciled paired closes from the active family." Any
aggregation that cannot name which tier each row came from must not be allowed to
produce that number.

## Verification

```bash
python scripts/trade_graph.py --build
python scripts/trade_graph.py --losses   # scorable 162, excluded {'journal': 2}, n=1
python -m pytest tests/test_temporal_trade_graph.py -q
```
