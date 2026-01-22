# LL-282: Use close_position() API for Closing Orphan Positions

**ID**: LL-282
**Date**: 2026-01-22
**Severity**: CRITICAL
**Category**: trading-operations
**Tags**: alpaca, api, close_position, options, orphan-positions, timeInForce

## Summary

When closing options positions via Alpaca API, use `client.close_position(symbol)` instead of `client.submit_order(MarketOrderRequest(...))`. The `close_position()` method automatically handles:
1. Order side detection (SELL for long, BUY for short)
2. Correct quantity (liquidates entire position)
3. Proper order parameters

## Root Cause

Multiple issues combined to prevent orphan positions from closing:
1. **Wrong API method**: Using `submit_order()` required manual side detection and quantity specification
2. **Wrong TimeInForce**: Using `TimeInForce.GTC` (Good Till Canceled) which is NOT supported for options - must use `TimeInForce.DAY`
3. **No scheduled retry**: Workflows only ran on manual trigger, not during market hours

## Impact

- SPY260220P00658000: 8 long puts with -$1,240 unrealized loss
- Position remained open for multiple sessions despite "successful" workflow runs
- Orders were submitted but never filled

## Solution

1. Replace `submit_order(MarketOrderRequest(...))` with `close_position(symbol)`:
```python
# OLD (broken):
order_request = MarketOrderRequest(
    symbol=option_symbol,
    qty=qty,
    side=close_side,
    time_in_force=TimeInForce.GTC  # NOT supported for options!
)
order = client.submit_order(order_request)

# NEW (correct):
result = client.close_position(option_symbol)
```

2. Use `TimeInForce.DAY` for any options orders (GTC not supported)

3. Add scheduled triggers to close workflows for auto-healing during market hours

## Files Modified

- `.github/workflows/emergency-close-options.yml` - Now uses close_position()
- `scripts/close_orphan_put.py` - Now uses close_position()
- `scripts/close_orphan_spy_puts.py` - Now uses close_position()
- `.github/workflows/close-excess-long-puts.yml` - Added schedule trigger

## Prevention

1. Always use `close_position()` API for liquidating entire positions
2. Always use `TimeInForce.DAY` for options orders
3. Add scheduled triggers to critical close workflows
4. Test position closing logic during market hours, not after-hours
5. Monitor order status (filled vs pending) after submission

## Key Insight

The Alpaca `close_position()` method is designed specifically for position liquidation and handles edge cases automatically. Using `submit_order()` for closing positions introduces unnecessary complexity and potential failure modes.

## Related Lessons

- LL-168: Alpaca options no trailing stop
- LL-217: Options risk monitor paper arg crisis
- LL-221: Orphan put crisis Jan 15
- LL-278: Position imbalance crisis Jan 21
