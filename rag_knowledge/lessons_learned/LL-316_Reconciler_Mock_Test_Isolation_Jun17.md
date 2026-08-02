# LL-316: Reconciler Mock Test Isolation

**ID**: LL-316
**Date**: 2026-06-17
**Severity**: HIGH
**Category**: reconciliation, testing, mock-data
**Status**: RESOLVED
**Related PR**: #4133
**Merge Commit**: e0f10dc46f8f2a2f4b81bd4bd8941b8ca8f233c6

## Incident Summary

The daily broker-vs-paired P/L reconciliation script (`scripts/reconcile_broker_vs_paired.py`) reported a massive breach on `main` where the computed broker realized P/L was `$960.56` instead of the expected `-$-8093.00`, resulting in a delta of `$8927.06` against the paired ledger. 

This occurred because historical non-SPY-option fills (such as real stock fills `EQIX`, `DLR`, `CCI`, `SPY` and the option `AAPL260220P00430000`) were incorrectly categorized as "mock tests" and included in the realized P/L calculation instead of being filtered out.

## Root Cause

To prevent unit tests from failing due to their mock symbols (e.g. `S1`, `S2`, `A`, `B`, etc. which do not conform to the `SPY` option naming conventions), the reconciler implemented an `is_mock_test` logic:
```python
if not (symbol.startswith("SPY") and len(symbol) > 5):
    is_mock_test = True
```
Fills that matched `is_mock_test` bypassed the strict SPY options check. However, in production runs, this logic also matched real historical stock fills (like `EQIX`, `DLR`, `CCI`, `SPY`) and non-SPY options (like `AAPL260220P00430000`) in `trade_history`, causing their cash flows to be included.

## Fix

Scoped the mock-test bypass logic strictly to execution environments where `pytest` is loaded:
```python
is_pytest = "pytest" in sys.modules
is_mock_test = False
if is_pytest:
    # (previous mock symbol check logic here)
```
If `is_pytest` is `False` (production runs), `is_mock_test` is guaranteed to be `False`, enforcing strict filtering to SPY options only and excluding all other symbols.

## Verification

Targeted reconciliation tests run locally:
```text
uv run pytest tests/unit/test_reconciliation.py -v
6 passed in 0.16s
```

Run reconciler script directly on production ledger:
```text
uv run python3 scripts/reconcile_broker_vs_paired.py
INFO Reconciliation report written: /Users/igorganapolsky/workspace/git/igor/trading/data/reports/reconciliation_2026-06-18.json
INFO broker=$-8093.00  paired_in=$-7966.50  paired_out=$-63.00  delta=$-126.50  threshold=$150.00  window=[2026-01-22 17:48:41.448722+00:00, 2026-05-06 15:54:59.512970+00:00]
```
The reconciler correctly exits with `0` (reconciled within `$150.00` threshold).

## Prevention Rules

1. Symbol-based heuristics to identify mock tests must always be guarded by checking if the process is running under pytest (`"pytest" in sys.modules`).
2. Production data reconciliations must strictly exclude any asset class (e.g., stocks) or symbols (e.g., non-SPY option underlyings) that are outside of the active default trading scope.
