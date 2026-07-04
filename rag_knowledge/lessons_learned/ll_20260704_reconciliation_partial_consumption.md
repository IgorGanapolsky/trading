# LL-20260704: Reconciliation Partial-Consumption Diagnostics

**Date**: 2026-07-04
**Severity**: HIGH
**Scope**: Broker-vs-paired reconciliation, ML/RAG trading gate, weekend readiness

## Summary

The fastest safe path to "make money faster" was not trade execution because the
market was closed and the ML/RAG gate still blocked trading. The actionable
readiness work was to make the broker-vs-paired reconciliation alert explain
the remaining ledger gap faster.

## Evidence

- `scripts/deep_research_ml_rag.py --date 2026-07-04 --dry-run` returned
  `BLOCKED`: win rate `16.8%`, expectancy `$-32.21/trade`, and profit factor
  `0.70`.
- `scripts/reconcile_broker_vs_paired.py --date 2026-07-04` still alerted:
  broker P/L `-$1420.00`, paired in-window P/L `-$3926.00`, delta `$2506.00`,
  threshold `$150.00`.
- The new diagnostic fields identified:
  - `paired_underconsumed_order_count=3`
  - `paired_underconsumed_qty=10.0`
  - `paired_partial_unconsumed_cash=-1658.0`
  - `paired_overconsumed_order_count=7`
  - `paired_overconsumed_qty=7.0`
  - `paired_unpaired_order_count=15`

## Lesson

Over-consumed paired order references are ledger-integrity signals, not cash.
They must be reported separately and excluded from P/L reconciliation. Only
under-consumed fill quantity can contribute remaining cash to the paired
in-window bucket.

## Next Action

Investigate the 3 under-consumed fills, 7 over-consumed paired references, and
15 unpaired orders before any attempt to scale paper trading. Green code checks
do not override these data blockers.
