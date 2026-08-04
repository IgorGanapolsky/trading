# LL-361: Graph RAG Exposed a 94% Exit-Reason Instrumentation Gap

**Date**: August 3, 2026
**Category**: RAG / Data Integrity / Post-Mortem
**Severity**: HIGH
**Related**: LL-323, kill-criteria.md, data-integrity.md

## Summary

A temporal knowledge graph was built over the system's own causal history (trades,
policy windows from git, lessons) to answer multi-hop questions vector RAG cannot.
The first query it ran revealed that **154 of 164 trades have no recorded exit reason
(6.1% coverage)**. The realized loss of 7,662 USD on `iron_condor` cannot be attributed
to any exit path, because the attribution data was never written.

## Key Findings

| Finding                                  | Value                        |
| ---------------------------------------- | ---------------------------- |
| Trades in graph                          | 164 (162 ledger + 2 journal) |
| Exit reason recorded                     | 10 (6.1%)                    |
| `iron_condor` realized P/L               | -7,662 USD (n=161, PF 0.167) |
| Losses attributable to a known exit path | 1 (`stop_loss`, -267 USD)    |
| Policy windows recovered from git        | 20                           |

### Tightest stop-loss cohort bled the most

Cohorts split by the `IRON_CONDOR_STOP_LOSS_MULTIPLIER` value in force at entry:

| Value | Window                   | n   | Wins | Realized P/L | Expectancy |
| ----- | ------------------------ | --- | ---- | ------------ | ---------- |
| 1.0   | 2026-02-16 to 2026-02-25 | 9   | 2    | -369 USD     | -41.00 USD |
| 2.0   | 2026-02-25 to 2026-03-01 | 15  | 4    | -767 USD     | -51.13 USD |
| 1.0   | 2026-03-01 to 2026-04-08 | 129 | 10   | -6,520 USD   | -50.54 USD |

**This is observational, not causal.** The cohorts are not randomized, the windows
differ in market regime, and other parameters changed inside them. It is a hypothesis
generator, not evidence that a stop-loss value caused the losses.

## Root Cause

The exit path was never journaled for iron-condor closes. `data/trades.json` carries
`realized_pnl` and `outcome`, but `exit_reason` was only added later and only populated
for the active bull-put family and a handful of manual closes. Post-mortem attribution
is therefore impossible for the killed strategy's entire cohort.

## Prevention

1. `src/rag/graph/` records a missing exit path as `unrecorded` and **never** infers it
   from the P/L sign. Locked by `test_exit_reason_is_never_inferred`.
2. `loss_attribution()` reports `exit_reason_coverage` on every call, so a table built
   on 6% of the data cannot read as complete.
3. `scripts/check_exit_reason_coverage.py` fails when coverage regresses below the
   recorded baseline, so newly closed structures must journal an exit path.
4. Cohort ratios (win rate, profit factor) are withheld below n=30, mirroring the
   promotion gate. Locked by `test_ratios_withheld_below_minimum_sample`.
5. A policy window **closes** when its constant stops being a readable literal, so
   trades after a refactor get no `GOVERNED_BY` edge instead of being attributed to a
   stale value. Locked by `test_policy_window_closes_when_value_stops_being_a_literal`.

## Secondary Lesson: The Graph Found a Bug In Itself

The first build attributed 140 trades to `IRON_CONDOR_STOP_LOSS_MULTIPLIER = 1.0`. The
effective runtime value is **2.0** (it resolves through `ACTIVE_IRON_CONDOR_PROFILE`).
The extractor had read the last _literal_ in git (set 2026-03-01) and left that window
open forever, straight through the 2026-04-08 refactor that replaced the literal with a
profile lookup. 99 false `GOVERNED_BY` edges were being minted.

**A derived value that silently outlives its source is worse than a missing one.**
Unknown must be representable, and it must be reported — `indeterminate_since` now names
all 12 affected parameters and the date attribution stops.

## Operator

```bash
python scripts/trade_graph.py --build
python scripts/trade_graph.py --losses
python scripts/trade_graph.py --policy IRON_CONDOR_STOP_LOSS_MULTIPLIER
python scripts/check_exit_reason_coverage.py
```

## What This Does Not Justify

No projection, no claim of edge, and no change to the active bull-put validation, which
stands at n=3 — far below the n>=30 gate. The graph explains history; it does not
create evidence.
