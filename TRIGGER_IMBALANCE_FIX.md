# Trigger: Fix Position Imbalance

**Created**: Jan 22, 2026
**Reason**: LL-282 Crisis - 8 long puts vs 2 short puts imbalance
**Action**: Close 6 excess SPY260220P00658000 long puts

## Problem
Position: SPY260220P00658000
- Current: 8 LONG contracts
- Should be: 2 contracts (to match 2 short 653 puts)
- Excess: 6 contracts causing -$1,248 unrealized loss

## Expected Result
Close 6 SPY260220P00658000 to balance position to 2:2 ratio.

This file will be deleted after workflow completes.
