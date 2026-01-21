# LL-281: CALL Leg Pricing Fix - Aggressive Fallbacks

**Date**: January 21, 2026
**Severity**: HIGH
**Category**: Trading Execution
**Status**: FIXED

## What Happened

Iron condors were placing PUT legs successfully but CALL legs were failing:
- PUT spreads filled (565/570, 653/658)
- CALL spreads never filled (no CALL positions in portfolio)
- Result: Orphan puts with directional downside risk

## Root Cause

1. **Fallback price too low**: When option quotes weren't available, fallback was $1.50
2. **CALL options are more expensive**: 15-delta CALLs typically cost $3-5, not $1.50
3. **No quote validation**: System accepted $0 bids/asks without fallback

## Evidence

From system_state.json:
- SPY260220P00565000: -2 contracts (PUT)
- SPY260220P00570000: +3 contracts (PUT)
- SPY260220P00653000: -6 contracts (PUT)
- SPY260220P00658000: +6 contracts (PUT)
- **NO CALL OPTIONS**

## Fix Applied

1. **Detect CALL vs PUT**: Check symbol for "C" to identify calls
2. **Higher CALL fallback**: $4.00 for CALLs vs $2.00 for PUTs
3. **Price buffer**: Add 10% buffer on BUY orders to ensure fills
4. **Quote validation**: Check for $0 bids/asks before using

```python
# Before (both types)
fallback = 1.50

# After (type-specific)
if is_call:
    fallback = 4.00  # CALLs are more expensive
else:
    fallback = 2.00  # PUTs
```

## Prevention

1. **Use realistic fallbacks**: Match typical option prices for each type
2. **Add price buffers**: Ensure aggressive enough for fills
3. **Validate quotes**: Don't use $0 prices
4. **Log failures clearly**: Show which leg type failed and why

## Code Location

- `scripts/iron_condor_trader.py` - `get_option_price()` function

## Related Lessons

- LL-279: Partial Iron Condor Auto-Close
- LL-280: Position Limit Contract Counting
