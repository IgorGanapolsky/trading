# Lesson Learned: Prevent Duplicate Short Positions

**ID**: ll_169
**Date**: 2026-01-13
**Category**: Risk Management
**Severity**: CRITICAL

## Context
CEO observed a pending SELL order on an option contract that was ALREADY SHORT:
- Position: SOFI260206P00024000 (short 1 put at $0.80)
- Pending order: "SOFI260206P00024000 Limit @ $0.79, sell, 1.00"

This would have DOUBLED the risk exposure by selling another put on the same contract.

## Root Cause
The `execute_cash_secured_put` function in `simple_daily_trader.py` did not check for:
1. Existing short positions on the same contract
2. Pending SELL orders on the same contract

## Impact
- Could double risk exposure on losing positions
- Violates Phil Town Rule #1: Don't Lose Money
- Amplifies losses instead of managing them

## Solution (PR in progress)
Added safety checks before submitting SELL TO OPEN orders:

```python
# Check for existing short position
existing_positions = client.get_all_positions()
for pos in existing_positions:
    if pos.symbol == put_contract and float(pos.qty) < 0:
        logger.error(f"BLOCKED: Already SHORT {put_contract}")
        return None

# Check for pending SELL orders
open_orders = client.get_orders()
for order in open_orders:
    if order.symbol == put_contract and str(order.side).lower() == "sell":
        logger.error(f"BLOCKED: Pending SELL order exists")
        return None
```

## Prevention
1. Always check existing positions before opening new ones
2. Always check pending orders before submitting new ones
3. NEVER add to losing positions (Rule #1)
4. Add position-aware guards at trade execution layer

## Related
- ll_168: Alpaca options no trailing stop
- Phil Town Rule #1: Don't Lose Money
- Phil Town Rule #2: Don't Forget Rule #1
