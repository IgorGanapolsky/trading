# LL-168: Alpaca Does NOT Support Trailing Stops for Options

**ID**: ll_168
**Date**: 2026-01-13
**Category**: Risk Management
**Severity**: CRITICAL

## Context
Workflow logs showed all options positions being SKIPPED with error:
`"code":42210000,"message":"invalid order type for options trading"`

Result: **All option positions were UNPROTECTED**, violating Phil Town Rule #1.

## Root Cause
Alpaca's API does not support TrailingStopOrderRequest for options contracts.
The set_trailing_stops.py script was using trailing stops for ALL positions,
but options require a different order type.

## Impact
- SOFI260130P00025000: -$7.00 unrealized loss (UNPROTECTED)
- SOFI260220P00024000: -$5.00 unrealized loss (UNPROTECTED)
- Total unprotected loss: -$12.00+

## Solution (PR #1610)
Use GTC Limit orders for options instead of trailing stops:
- Short options: Buy-to-close at 1.5x current price (50% max loss)
- Long options: Sell at 0.5x current price (50% trailing)

```python
if is_option_symbol(symbol):
    stop_price = round(current_price * 1.5, 2)  # 50% max loss
    order_request = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=order_side,
        type="limit",
        time_in_force=TimeInForce.GTC,
        limit_price=stop_price,
    )
```

## Prevention
1. Always test order types against Alpaca's options API limitations
2. Check workflow logs for "42210000" error codes
3. Verify stop-loss orders are actually placed, not skipped

## Related
- Phil Town Rule #1: Don't Lose Money
- PR #1610: Fix options stop-loss
