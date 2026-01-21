# LL-278: Position Imbalance Crisis - Orphan Long Puts

**Date**: January 21, 2026
**Severity**: CRITICAL
**Category**: risk-management, execution-failure

## The Crisis

Portfolio lost $329.42 (-6.59%) due to position imbalance:

| Position | Qty | P&L |
|----------|-----|-----|
| SPY260220P00653000 (short) | -4 | +$402 |
| SPY260220P00658000 (long) | +6 | -$594 |

**Issue**: 6 long puts vs 4 short puts = **2 orphan long puts**

The orphan longs are decaying and losing money without corresponding short premium to offset.

## Root Cause Analysis

1. Trade execution submitted 6 long puts but only 4 short puts filled
2. OR partial fills weren't detected and corrected
3. Position monitoring didn't catch the imbalance

## Immediate Actions Required

1. Close the 2 excess long puts (SPY260220P00658000)
2. Verify all other positions are balanced
3. Add position balance validation to daily workflow

## Prevention

1. **Pre-trade validation**: Verify both legs have equal quantities
2. **Post-trade validation**: Check position balance immediately after execution
3. **Daily monitoring**: Run balance check before market open
4. **Test coverage**: `test_system_state_has_balanced_positions` must pass

## Phil Town Rule #1 Violation

This violates "Don't lose money" - orphan positions bleed capital.

## Lesson

Always verify position balance after EVERY trade execution. Partial fills are dangerous.
