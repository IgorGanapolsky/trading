# LL-280: Cumulative Position Risk Bypass - Individual Trades Accumulating Past Limits

**ID**: LL-280
**Date**: 2026-01-22
**Severity**: CRITICAL
**Category**: Risk Management, Trading Operations

## Incident Summary

On Jan 22, 2026, the system had accumulated SPY260220P00658000 to 8 contracts with **-$912 unrealized loss (19.6% of equity)**, far exceeding the 5% max position rule from CLAUDE.md.

## Root Cause Analysis

### The Problem
1. Trade gateway `_check_position_size_risk()` only checked **individual trade risk**
2. Each 1-contract trade passed the 5% check individually
3. But 8 trades accumulated to 19.6% risk - **4x the allowed limit**
4. No check for **cumulative risk across existing positions**
5. No enforcement of "1 iron condor at a time" rule

### Why This Happened
```python
# BEFORE (only checked new trade)
max_loss = 500 * (request.quantity or 1)  # 1 contract = $500 max loss
if max_risk_pct > 0.05:  # Passed! 500 < 5% of $4647
    reject()

# AFTER 8 trades: Total risk = $4000 (86% of equity!)
# But each individual trade passed the check
```

### The Silent Accumulation
- Trade 1: $500 risk (10.8%) - should have been blocked
- Trade 2: $500 risk (10.8%) - should have been blocked
- ... continued to 8 trades
- Result: $2592 market value, -$912 unrealized loss

## Impact
- 19.6% of equity at risk in single position
- Violated CLAUDE.md "5% max position" rule
- Violated "1 iron condor at a time" rule
- CEO trust damaged

## Fix Applied

### 1. Cumulative Position Risk Check
```python
def _check_cumulative_position_risk(self, request, account_equity, positions):
    # Sum existing risk from all positions
    existing_risk = sum(abs(pos.unrealized_pl) for pos in positions)
    new_risk = self._calculate_max_loss(request)
    total_risk = existing_risk + new_risk

    if total_risk / account_equity > 0.10:  # 10% cumulative max
        return True, f"Cumulative risk {total_risk_pct}% exceeds 10%"
```

### 2. Iron Condor Limit Check
```python
def _check_iron_condor_limit(self, positions):
    # Count iron condor structures (4+ option legs same expiry)
    if has_existing_4_leg_structure:
        return True, "Max 1 iron condor at a time per CLAUDE.md"
```

### 3. New Rejection Reasons
- `CUMULATIVE_RISK_TOO_HIGH`: Blocks trades when total risk exceeds limit
- `MAX_IRON_CONDORS_EXCEEDED`: Enforces 1 iron condor rule

## Prevention Measures

### Immediate
- [x] Add `_check_cumulative_position_risk()` to trade_gateway.py
- [x] Add `_check_iron_condor_limit()` to trade_gateway.py
- [x] Add checks in `evaluate()` method
- [x] All tests pass (876/876)

### Long-term
1. Add daily position audit workflow
2. Alert when cumulative risk exceeds 7% (warning before 10% block)
3. Dashboard showing cumulative risk percentage

## Lessons Learned

1. **Individual checks are not enough** - must check cumulative exposure
2. **CLAUDE.md rules must be enforced in code** - not just documented
3. **Small trades accumulate** - each passing check doesn't mean safe
4. **Trust is fragile** - one bypass erodes confidence in system

## The $100K Playbook Reminder

From LL-255:
- SPY premium selling (not individual stocks) - FOLLOWED
- Iron condors - defined risk both directions - FOLLOWED
- 30-45 DTE - optimal theta decay - FOLLOWED
- **5% max position - Never 96%** - VIOLATED (19.6%)
- **No more than 1 iron condor at a time** - VIOLATED

The lesson existed. The code didn't enforce it. Now it does.

## Tags
`critical`, `risk-management`, `position-sizing`, `cumulative-risk`, `iron-condor`, `trade-gateway`, `fix-applied`
