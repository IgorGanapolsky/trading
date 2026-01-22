# LL-290: Position Accumulation Bug - Iron Condor Trader

**Date**: January 22, 2026
**Severity**: CRITICAL
**Category**: Position Management, System Bug, Risk Control
**Status**: RESOLVED

## Context

iron_condor_trader.py was placing partial fills that accumulated to 8 contracts instead of max 4.

## Root Cause

Position limit check happened inside execute() but multiple workflow runs could race. Partial fills were not properly cleaned up.

**Key failures:**
1. Position check was INSIDE execute() - too late
2. No file-based lock to prevent concurrent executions
3. Partial fills accumulated without detection
4. Multiple workflow runs could race condition

## Impact

**$1,312 loss on SPY260220P00658000** - 8 long puts accumulated when max should be 2.

This is a Phil Town Rule #1 violation - the system lost money due to a preventable bug.

## Root Cause Analysis

| Component | Failure |
|-----------|---------|
| Position check timing | Inside execute(), not before |
| Concurrency control | No lock file |
| Partial fill handling | Not cleaned up |
| Workflow orchestration | Race conditions possible |

## Prevention

1. **Check positions BEFORE entering execute()** - fail fast if any positions exist
2. **If ANY option positions exist, skip new trades** - conservative approach
3. **Add file-based lock to prevent concurrent executions** - single execution guarantee
4. **Clean up partial fills immediately** - no accumulation allowed
5. **Add position count validation in pre-trade checks** - enforce limits strictly

## Code Changes Required

```python
# BEFORE execute():
existing_positions = get_option_positions()
if existing_positions:
    logger.warning(f"Existing positions found: {existing_positions}, skipping trade")
    return

# Add file lock:
import fcntl
with open('/tmp/iron_condor_trader.lock', 'w') as lock_file:
    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    # execute trade logic here
```

## Verification Checklist

- [ ] Position check moved BEFORE execute()
- [ ] File-based lock implemented
- [ ] Partial fill cleanup logic added
- [ ] Max position validation in pre-trade gate
- [ ] Test with concurrent workflow simulations

## Phil Town Rule #1 Compliance

This bug violated "Don't lose money" - $1,312 loss was preventable.

**Lesson**: Position limits MUST be enforced at ENTRY, not inside execution.

---

## Tags

`iron_condor`, `position_limit`, `accumulation`, `partial_fill`, `CRITICAL`, `race_condition`, `concurrency`
