# LL-276: Day 2 Crisis - Position Imbalance and Missing CALL Legs

**Date:** January 21, 2026
**Severity:** CRITICAL
**Category:** Position Management, Iron Condor Structure

## Issue
Two consecutive days of trading crises:
- Day 1 (Jan 20): SOFI position blocking trades (orphan from Jan 12-13)
- Day 2 (Jan 21): Iron condor has ONLY PUT positions, NO CALL positions

## Current State (Jan 21, 4:55 PM ET)
```
Portfolio: $5,033.91
Positions: 5 PUT options, 0 CALL options

SPY: 2.58 shares
SPY260220P00565000: -3 short puts
SPY260220P00570000: +2 long puts
SPY260220P00653000: -2 short puts
SPY260220P00658000: +4 long puts
```

This is NOT an iron condor - it's a collection of put spreads with no call hedging.

## Root Causes Identified
1. **Argparse bug (fixed)**: `--symbol` argument missing caused silent script failures
2. **Incomplete execution**: Only PUT legs filled, CALL legs never placed
3. **No validation**: System didn't verify 4-leg structure before continuing

## Actions Taken
1. Fixed argparse --symbol bug (PR #2475)
2. Created orphan cleanup workflow
3. Triggered cleanup workflows
4. Cleaned up stale branches (10 → 1)
5. Tests now pass: 858 passed, 1 failed (position-related)

## Remaining Issue
The 1 failing test (`test_system_state_has_balanced_positions`) is CORRECT - we have 5 PUT positions but 0 CALL positions. This violates iron condor structure.

## Fix Required
1. Close ALL existing option positions (clean slate)
2. Place a COMPLETE iron condor with ALL 4 legs
3. Add pre-trade validation that rejects partial fills

## Prevention
1. Add `if len(filled_legs) != 4: abort_and_cleanup()` logic
2. Verify BOTH put AND call spreads exist before marking trade complete
3. Add alerting when position count doesn't match expected (4 legs per IC)

## Related
- LL-268: Iron condor execution failure
- LL-275: Argparse --symbol missing
- LL-270: System blocked, no auto cleanup
