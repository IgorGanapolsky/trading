# LL-297: Incomplete Iron Condor Crisis (PUT-only positions) - January 23, 2026

**Date**: January 23, 2026
**Severity**: CRITICAL
**Category**: Position Management, Iron Condor Execution
**Status**: IN_PROGRESS

## Issue Summary

The system has 3 open PUT-only positions instead of a proper 4-leg iron condor:
- SPY260220P00565000: -1 (short put) @ $0.31
- SPY260220P00570000: +1 (long put) @ $0.33
- SPY260220P00658000: +1 (long put) @ $2.69

**Current P/L**: -$3.26 (-0.01%)

This is NOT an iron condor - it's a bearish position that requires SPY to fall to profit.

## Root Cause

Same issue as LL-276: Iron condor execution only placed PUT legs, CALL legs never executed.
Possible causes:
1. CALL leg orders rejected due to pricing
2. Partial execution not detected
3. System didn't validate 4-leg structure

## Impact

- CEO Crisis Mode: "We have to make money today!!!!"
- Trust erosion: "Four days of crisis in a row"
- Position imbalance creates directional (bearish) risk instead of neutral theta decay

## Actions Taken

1. Triggered `FORCE_CLOSE.trigger` to initiate position cleanup
2. Updated `TRIGGER_TRADE.md` to trigger proper iron condor execution
3. Pushed to branch `claude/fix-trading-rag-system-rLzJT`
4. Workflows should execute:
   - `force-close-position.yml` - close existing positions
   - `daily-trading.yml` - execute proper 4-leg iron condor

## Prevention (Required Implementation)

1. **Pre-execution validation**: Before marking trade complete, verify exactly 4 legs exist
2. **Auto-rollback**: If < 4 legs fill, automatically close partial positions
3. **Position structure check**: Add test that validates PUT count == CALL count
4. **Alerting**: Send notification if iron condor is incomplete after execution

## Phil Town Alignment

- Rule #1: Don't lose money - -$3.26 is essentially break-even, but directional risk violates neutral strategy
- Capital Preservation: Incomplete iron condors have unbounded directional risk on one side
- Proper iron condors have DEFINED risk on BOTH sides

## Resolution Status

- [ ] Close existing 3 PUT positions
- [ ] Execute complete 4-leg iron condor
- [ ] Verify P/L turns positive
- [ ] Add position structure validation

## Related Lessons

- LL-276: Day 2 Crisis - Position Imbalance and Missing CALL Legs
- LL-268: Iron Condor Execution Failure
- LL-279: Partial Iron Condor Auto-Close

## Tags

`iron-condor`, `position-management`, `crisis`, `incomplete-execution`, `PUT-only`
