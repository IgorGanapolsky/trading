# LL-175: Trade Gateway Rule #1 Enforcement Fixed

**ID**: ll_175
**Date**: 2026-01-13
**Severity**: CRITICAL
**Type**: Bug Fix

## Problem

Trade gateway only blocked BUY orders when P/L was negative. But short puts (SELL orders on options) also increase risk and were bypassing the Rule #1 check.

## Evidence

- SOFI260206P00024000: 2 short puts opened despite -$30 P/L
- `request.side == "buy"` check missed SELL orders that open short positions

## Root Cause

```python
# OLD CODE (broken)
if request.side.lower() == "buy":
    if total_pl < 0:
        # Block...
```

Short puts have `side="sell"` but are risk-increasing like buys.

## Fix Applied

```python
# NEW CODE (fixed)
is_risk_increasing = (
    request.side.lower() == "buy"
    or (request.is_option and request.side.lower() == "sell")  # Short puts/calls
)

if is_risk_increasing and total_pl < 0:
    # Block...
```

## Also Added

- CHECK 2.5: Duplicate short position prevention
- Max 1 CSP per underlying symbol
- Prevents doubling down on losing positions

## Verification

```
Test 1: Block short put when P/L negative... ✅ PASS
Test 3: Block duplicate short position... ✅ PASS
```

## Prevention

1. All risk-increasing trades now blocked when P/L < 0
2. Max 1 short position per underlying enforced
3. Both checks work together with RAG critical lessons

## Tags

critical, rule-1, trade-gateway, bug-fix, risk-management, short-puts
