# LL-279: Partial Iron Condor Auto-Close

**Date**: January 21, 2026
**Severity**: CRITICAL
**Category**: Trading Execution
**Status**: FIXED

## What Happened

Iron condors were being placed with only PUT legs filling. CALL legs were failing silently, leaving dangerous directional positions:
- Long puts + short puts = bull put spreads only
- Missing bear call spreads = no upside protection
- Result: Orphan puts causing losses when market rises

## Root Cause

1. CALL option orders were failing (likely due to pricing/liquidity)
2. The code logged "ACTION REQUIRED: Close partial position" but **DID NOT ACTUALLY CLOSE IT**
3. System continued operating with partial fills = directional risk

## Evidence

From `system_state.json` positions:
- SPY260220P00565000: -2 (short put)
- SPY260220P00570000: +3 (long put)
- SPY260220P00653000: -6 (short put)
- SPY260220P00658000: +6 (long put)
- **NO CALL OPTIONS AT ALL**

Unrealized P/L on options: ~-$181 (net loss)

## Fix Applied

Added auto-close logic to `scripts/iron_condor_trader.py`:
1. When only 2-3 legs fill (instead of 4), immediately cancel/close
2. First try to cancel pending orders
3. If already filled, submit market order to reverse position
4. Log all cleanup actions for audit trail

## Prevention

1. **ALWAYS verify all 4 legs**: Iron condor = 4 legs, period
2. **Auto-close partial fills**: Don't leave directional risk overnight
3. **Monitor for imbalances**: Alert when position counts don't match
4. **Market orders for cleanup**: Use market orders when closing failed positions (speed > price)

## Code Location

- `scripts/iron_condor_trader.py` lines 446-500 (approximate)

## Related Lessons

- LL-268: Iron Condor Win Rate Research
- LL-276: Day 2 Crisis - No CALL legs
- LL-278: Position Imbalance Crisis
