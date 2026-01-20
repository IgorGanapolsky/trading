# LL-254: is_market_holiday() Incorrectly Blocked Pre-Market Trading

## Date
January 16, 2026

## Category
CRITICAL BUG FIX

## Summary
The `is_market_holiday()` function in `scripts/autonomous_trader.py` was blocking all trading when the workflow ran before market open (9:30 AM ET), incorrectly treating "market not yet open" as "market holiday."

## Root Cause
```python
# OLD (BROKEN) CODE:
return not clock.is_open  # Market closed on weekday = holiday
```

This returned `True` whenever the market was currently closed, including:
- Before 9:30 AM ET (market not yet open)
- After 4:00 PM ET (market already closed)
- Actual holidays (MLK Day, etc.)

The scheduled workflow runs at **13:35 UTC (8:35 AM ET)** - 55 minutes before market open. At this time:
- `clock.is_open = False` (market hasn't opened yet)
- Function returned `True` ("it's a holiday")
- Trading was skipped with "Markets closed - skipping equity trading"

## Impact
- **No trades executed** on Friday January 16, 2026 during the 13:35 UTC run
- System appeared healthy but was silently skipping trades
- Only the 14:35 UTC run (9:35 AM ET, market open) would work

## Fix Applied
```python
# NEW (FIXED) CODE:
# If next_open is today, it's not a holiday - just waiting for 9:30 AM
if next_open_date == today_utc:
    return False  # Proceed with trading

# Next open is in the future (tomorrow+), so today is a holiday
return True
```

The fix checks if the market is **scheduled** to open today by comparing `clock.next_open` date to today's date:
- If `next_open` is today → Just waiting for market open → NOT a holiday → Trade
- If `next_open` is tomorrow+ → Actual holiday → Skip trading

## PR Reference
- PR #2005: fix(trading): Fix is_market_holiday() blocking trades before market open

## Prevention
1. Test functions with time-dependent logic at multiple times of day
2. Consider adding unit tests for `is_market_holiday()` with mocked clock states:
   - Before market open (8:00 AM ET)
   - During market hours (10:00 AM ET)
   - After market close (5:00 PM ET)
   - On actual holidays
3. Monitor workflow logs for "Markets closed - skipping equity trading" on trading days

## Key Learning
**Never assume "market closed" means "holiday"** - markets are closed most of the day even on trading days. Check if the market will open today, not just if it's open right now.

## Tags
trading, bug-fix, is_market_holiday, scheduling, alpaca-api
