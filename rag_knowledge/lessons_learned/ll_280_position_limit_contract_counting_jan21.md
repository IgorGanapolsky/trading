# LL-280: Position Limit - Count Contracts Not Symbols

**Date**: January 21, 2026
**Severity**: CRITICAL
**Category**: Risk Management
**Status**: FIXED

## What Happened

The position limit check was counting UNIQUE SYMBOLS instead of TOTAL CONTRACTS:
- Before: `position_count = len(spy_option_positions)` = 4 (unique symbols)
- Reality: 17 total contracts across those 4 symbols
- Max allowed: 4 contracts (1 iron condor)

This allowed 4x overexposure and massive position accumulation.

## Evidence

From `system_state.json` positions:
```
SPY260220P00565000: qty = -2  (should be -1)
SPY260220P00570000: qty = +3  (should be +1)
SPY260220P00653000: qty = -6  (should be -1)
SPY260220P00658000: qty = +6  (should be +1)
```

**Total: 17 contracts when max is 4**

## Root Cause

1. `len(spy_option_positions)` counts unique symbols (4)
2. Actual exposure is `sum(abs(qty))` = 17 contracts
3. Multiple workflow runs placed additional trades each time
4. Position check SKIPPED on error instead of BLOCKING

## Fix Applied

1. **Count total contracts**: `sum(abs(int(float(p.qty))) for p in positions)`
2. **Block on error**: If position check fails, BLOCK trade (don't skip)
3. **Log position details**: Show each position's qty for debugging

## Code Location

- `scripts/iron_condor_trader.py` lines 303-365 (approximate)

## Prevention

1. **Always count contracts**: Never count just unique symbols
2. **Fail closed**: If safety check fails, block the action
3. **Log details**: Show exact positions when limit reached
4. **Single source of trade placement**: Reduce scripts that can place trades

## Related Lessons

- LL-279: Partial Iron Condor Auto-Close
- LL-278: Position Imbalance Crisis
