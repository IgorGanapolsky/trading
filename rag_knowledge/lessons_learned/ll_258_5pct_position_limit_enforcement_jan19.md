# LL-258: 5% Position Limit Must Be Enforced BEFORE Trade Execution

**Date**: 2026-01-19
**Severity**: CRITICAL
**Category**: Risk Management Bug

## Problem Found

The `execute-credit-spread.yml` workflow checked 15% total exposure but did NOT verify that the NEW trade being placed was within the 5% per-position limit.

**Example of bug**:
- Account equity: $5,000
- 5% limit = $250 max per position
- Workflow could place a $300 spread (6% = VIOLATION)
- Only blocked if TOTAL exposure exceeded 15%

## Root Cause

Compliance check was incomplete:
```python
# OLD CODE - Only checked total exposure
if risk_pct > MAX_EXPOSURE_PCT:  # 15% total
    exit(1)
# MISSING: Check if proposed trade exceeds 5% per-position!
```

## Fix Applied

Added per-position check BEFORE total exposure check:
```python
# Check 5% per-position limit BEFORE placing trade
if proposed_risk > max_per_position:
    print("POSITION SIZE VIOLATION")
    exit(1)
```

## Verification

With $5K account:
- Max per position: $250 (5%)
- $3 spread = $300 collateral
- NEW CODE: Blocks trade (6% > 5%)
- OLD CODE: Would have allowed it

## Phil Town Rule #1 Alignment

This fix ensures we NEVER risk more than 5% on a single position, even if total exposure is low. This is the core of capital preservation.

## Tags

risk-management, position-sizing, 5-percent-rule, rule-one, bug-fix
