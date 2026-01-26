# LL-316: Paper Trading Blocked by Overly Strict VIX Threshold

**ID**: LL-316
**Date**: 2026-01-26
**Severity**: CRITICAL
**Category**: trading-system, paper-trading
**Tags**: `vix`, `entry-conditions`, `paper-trading`, `crisis`
**Status**: RESOLVED

## Incident Summary

Paper trading phase went 5 days (Jan 22-26) with ZERO trades executed. The system was "working as designed" but the design prevented any trading during the validation phase.

## Root Cause

`VIX_OPTIMAL_MIN = 15` in `src/constants/trading_thresholds.py` blocked ALL iron condor trades when VIX was below 15. The entry condition check returns:

```python
if current_vix < RiskThresholds.VIX_OPTIMAL_MIN:
    return False, f"VIX {current_vix:.2f} < {RiskThresholds.VIX_OPTIMAL_MIN} (premiums too thin)"
```

During low volatility periods (VIX 12-14), this blocks all paper trading validation.

## Impact

- 5 consecutive trading days with $0 trades
- Paper trading validation cannot proceed
- Win rate stuck at 0% (no sample size)
- 90-day validation period wasted

## Resolution (Jan 26, 2026)

Lowered `VIX_OPTIMAL_MIN` from 15 to 12 in trading_thresholds.py:

```python
VIX_OPTIMAL_MIN = 12  # Allow paper trading even with thin premiums
```

Rationale:
- Paper trading is for validation, not profit optimization
- VIX 12-15 still allows tradeable premiums on SPY
- Better to trade with smaller premium than not trade at all during validation
- Live trading can use stricter threshold (15) after validation

## Prevention Measures

1. **Paper Trading Override**: Consider adding `PAPER_TRADING_MODE` flag that relaxes entry conditions
2. **Alert on No-Trade Days**: If 3+ consecutive days with no trades, alert CEO
3. **Force Trade Option**: Add workflow_dispatch option to force a trade regardless of VIX
4. **Weekly Trade Minimum**: During paper phase, ensure at least 1 trade per week

## Related Lessons

- LL-310: VIX Timing for Iron Condor Entry
- LL-269: Iron Condor Entry Signals
- LL-298: Share Churning Loss (opposite problem - too many trades)
