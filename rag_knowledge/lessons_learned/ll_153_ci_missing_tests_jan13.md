# LL-153: Three More Missing Test Files Blocking CI

**ID**: ll_153_ci_missing_tests_jan13
**Date**: 2026-01-13
**Severity**: CRITICAL

## Problem
CI workflow failing because these test files referenced in `ci.yml` do not exist:
- `tests/test_safety_matrix.py`
- `tests/test_rag_ml_safety.py`
- `tests/test_rag_ml_operational.py`

This blocked PR merges and prevented fixes from reaching main.

## Root Cause
Same pattern as ll_148: Workflows reference test files that were deleted or never created.

## Solution
Removed references from `.github/workflows/ci.yml` safety-matrix job.
Updated to only run `tests/test_safety_gates.py` which exists.

## Prevention
1. Run `python3 scripts/validate_test_references.py` before PR
2. Add CI step to verify all referenced test files exist
3. Use glob patterns instead of explicit file lists where possible

## Impact
- CI blocked for unknown duration
- PR merges blocked
- Compounds ll_148 (74+ days no trading)

## Tags
critical, ci, tests, blocking, workflow
