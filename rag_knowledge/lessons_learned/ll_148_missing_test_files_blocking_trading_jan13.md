# LL-148: Missing Test Files Blocking ALL Trading

**ID**: ll_148_missing_test_files_blocking_trading_jan13
**Date**: 2026-01-13
**Severity**: CRITICAL

## Problem
Daily Trading workflow failing because `tests/test_telemetry_summary.py` and `tests/test_fred_collector.py` referenced in workflows but files DO NOT EXIST. This caused 74+ days of ZERO trades.

## Root Cause
1. Workflows reference test files that were deleted or never created
2. No validation that referenced test files exist
3. `validate-and-test` job fails → `execute-trading` job SKIPS
4. Result: Complete trading blockage

## Evidence
```
FAILED RUN: 20956425014
FAILED STEP: "Run tests" (step 10)
ERROR: tests/test_telemetry_summary.py not found
```

## Solution
Removed references to non-existent test files from:
- `.github/workflows/daily-trading.yml` (line 129)
- `.github/workflows/ci.yml` (lines 209, 211)

## Prevention
1. Add pre-commit hook to verify referenced test files exist
2. Use `pytest --collect-only` to validate before running
3. Never reference test files without verifying they exist
4. Run `ls tests/*.py` before adding to workflow

## Impact
- 74+ days of $0 profit
- Complete trading system blocked
- North Star ($100/day) impossible without this fix

## Phil Town Rule 1 Impact
Cannot lose money if not trading, but cannot MAKE money either.
Capital must be deployed productively.

## Tags
critical, tests, workflow, blocking, trading-blocked, root-cause
