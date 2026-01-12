# Lesson Learned: Stale Order Threshold Must Be 4 Hours, Not 24

**ID**: ll_135_stale_order_threshold_fix_jan12
**Date**: 2026-01-12
**Severity**: HIGH
**PR**: #1523

## Problem
System had $5K in paper account but hadn't traded in 6 days. Root cause: unfilled orders sitting for 24 hours consumed all buying power, blocking new trades.

## Root Cause
With $5K capital and ~$2,500 per CSP collateral, we can only hold 2 positions. If 2 orders sit unfilled for 24 hours, buying power = $0 and no new trades can execute.

## Solution
Reduced MAX_ORDER_AGE_HOURS from 24 to 4 in scripts/cancel_stale_orders.py. Orders unfilled after 4 hours are cancelled to free buying power for new opportunities.

## Test Coverage
Added tests/test_cancel_stale_orders.py with:
- Verify threshold is 4h
- Stale order detection logic
- Fresh order preservation
- Buying power math for $5K account

## Prevention
- Monitor buying power before placing orders
- Auto-cancel stale orders every 4 hours
- Use credit spreads when buying power tight

## CEO Directive
"Why are we losing money and not making trades?" - This fix ensures trades can execute daily.
