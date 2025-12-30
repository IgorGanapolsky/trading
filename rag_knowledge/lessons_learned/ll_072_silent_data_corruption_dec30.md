# Lesson Learned: Silent Data Corruption from Simulated Fallback

**ID**: LL_072
**Date**: December 30, 2025
**Severity**: CRITICAL
**Category**: Data Integrity, System Reliability
**Tags**: alpaca, sync, data-corruption, silent-failure

## Incident Summary

The auto-sync script (`scripts/sync_alpaca_state.py`) silently overwrote real portfolio data ($100,810.04) with simulated data ($100,000) when Alpaca API keys were not available in the environment.

The system claimed "AUTO-SYNC SUCCESSFUL" while actually corrupting the data.

## Root Cause

1. **Silent fallback**: When no API keys found, script returned simulated $100k data instead of failing
2. **False success**: Script returned exit code 0 even when using fake data
3. **No validation**: Nothing verified the sync result was from real Alpaca vs simulated
4. **Environment gap**: Production hooks run without .env file loaded

```python
# THE BUG (lines 53-62 of sync_alpaca_state.py):
if not api_key or not api_secret:
    logger.warning("⚠️ No Alpaca API keys found - using simulated mode")
    return {"equity": 100000.0, ...}  # SILENTLY CORRUPTS DATA!
```

## Impact

- Real portfolio value ($100,810.04) overwritten with $100,000
- 7 days of stale data shown to user
- Trust violation: System lied about sync success
- Potential for catastrophic trading decisions based on wrong data

## Prevention Measures

1. **NEVER silently fallback to simulated data** - Fail loudly instead
2. **Verify sync mode** - Check `sync_mode` field before trusting data
3. **Backup before sync** - Always preserve previous state (already implemented)
4. **Validate result** - Compare synced values against last known values

## Fix Applied

```python
if not api_key or not api_secret:
    logger.error("❌ FATAL: No Alpaca API keys found!")
    raise RuntimeError("Missing Alpaca API credentials - cannot sync")
```

## Related Lessons

- LL_058: Stale data lying incident (Dec 23)
- LL_051: Blind trading catastrophe

## Verification

After fix, sync without credentials will:
1. Log FATAL error
2. Raise exception
3. Return non-zero exit code
4. Trigger circuit breaker BLOCK (not silent success)
