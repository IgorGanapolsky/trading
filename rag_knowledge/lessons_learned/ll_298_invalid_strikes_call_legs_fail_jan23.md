# LL-298: Invalid Option Strikes Causing CALL Legs to Fail

**Date**: January 23, 2026
**Severity**: CRITICAL
**Impact**: 4 consecutive days of losses (~$70 total)

## Summary
Iron condor CALL legs were not executing because calculated strikes ($724, $729) were invalid. SPY options have $5 strike increments for OTM options, so only $720, $725, $730, etc. exist.

## Root Cause
```python
# BROKEN CODE (before fix)
short_call = round(price * 1.05)  # round(690*1.05) = $724 INVALID!

# FIXED CODE
def round_to_5(x): return round(x / 5) * 5
short_call = round_to_5(price * 1.05)  # round_to_5(724.5) = $725 VALID!
```

## Evidence
- Trade history: 23 PUT trades, 0 CALL trades on Jan 23
- PUT strikes $655, $658 worked (happened to be valid)
- CALL strikes $724, $729 failed silently (invalid symbols)

## Symptoms
- Only PUT spread legs fill → directional risk
- Account loses money when SPY moves up
- No error logs (Alpaca silently rejects invalid symbols)

## Fix Applied
- Added `round_to_5()` function to `calculate_strikes()`
- All strikes now rounded to nearest $5 multiple
- Commit: `8b3e411` (PR pending merge)

## Prevention
1. Always round SPY strikes to $5 increments
2. Verify ALL 4 legs fill before considering trade complete
3. Add validation that option symbols exist before submitting orders
4. Log when any leg fails to fill

## Related
- LL-297: Incomplete iron condor crisis (PUT-only positions)
- LL-281: CALL leg pricing fallback

## Tags
iron_condor, options, strikes, call_legs, validation
