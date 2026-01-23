# LL-301: Iron Condor Position Management System Implementation

**Date**: January 23, 2026
**Category**: System Improvement, Position Management
**Severity**: HIGH
**Status**: IMPLEMENTED

## Summary

Created dedicated iron condor position management system with proper exit rules based on LL-268/LL-277 research. This addresses a critical gap where the existing `manage_positions.py` used equity-based thresholds inappropriate for options credit strategies.

## Gap Identified

**Before**: `manage_positions.py` used:
- 15% profit target (equity %)
- 8% stop-loss (equity %)
- 30 days max hold

**Problem**: These thresholds are for STOCKS, not OPTIONS. Options credit strategies need credit-based thresholds.

## Solution Implemented

Created `scripts/manage_iron_condor_positions.py` with proper exit rules:

| Rule | Threshold | Research Source |
|------|-----------|-----------------|
| Profit Target | 50% of credit received | LL-265 |
| Stop Loss | 200% of credit (2x) | CLAUDE.md |
| DTE Exit | 7 days to expiration | LL-268 |

## Components Created

1. **Script**: `scripts/manage_iron_condor_positions.py`
   - Parses OCC option symbols
   - Groups legs into iron condors by expiry
   - Calculates P/L as % of credit
   - Triggers exits based on rules

2. **Tests**: `tests/test_manage_iron_condor_positions.py`
   - 15 unit tests covering all exit conditions
   - Symbol parsing tests
   - DTE calculation tests

3. **Workflow**: `.github/workflows/manage-iron-condor-positions.yml`
   - Hourly during market hours (10 AM - 4 PM ET)
   - Safe replacement for disabled crisis workflows

## Why This Matters

The $22.61 loss on Jan 23 was caused by crisis workflows running aggressive schedules (every 5 minutes) trading SPY shares. This new system:

1. Monitors positions at reasonable intervals (hourly)
2. Uses correct thresholds for options strategies
3. Only triggers exits when rules are met
4. Does not churn positions unnecessarily

## Test Results

```
=========== 923 passed, 132 skipped ===========
```

All 15 new tests pass. Total test count increased from 898 to 923.

## Prevention

Before creating position management code:
1. Verify threshold type (% of price vs % of credit)
2. Use research-backed rules (LL-265, LL-268, LL-277)
3. Test with unit tests before deploying
4. Schedule at reasonable intervals (hourly, not per-minute)

## Related Lessons

- LL-265: Credit Spread Exit Strategies
- LL-268: Iron Condor Win Rate Research (7 DTE exit)
- LL-277: Iron Condor Optimization (86% win rate)
- LL-298: Share Churning Loss (why this was needed)

## Tags

`position-management`, `iron-condor`, `exit-rules`, `system-improvement`
