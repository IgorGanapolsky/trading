---
layout: post
title: "Lesson Learned: Simulated Sync Fallback Was Silently Lying"
date: 2025-12-29
---

# Lesson Learned: Simulated Sync Fallback Was Silently Lying

**Date**: December 29, 2025
**Severity**: CRITICAL
**Category**: Data Integrity, Trust

## Incident

The `sync_alpaca_state.py` script was silently falling back to simulated/fake data when Alpaca API keys were missing or connection failed. It would:

1. Detect missing API keys
2. Return fake data (equity=$100,000, positions=0)
3. Write this garbage to `system_state.json`
4. Return exit code 0 (success)
5. Hook would print "AUTO-SYNC SUCCESSFUL"

This caused the CEO to see his real $100,810 portfolio overwritten with fake $100,000 data, making him believe the system was losing money and lying.

## Root Cause

Lines 53-62 of `scripts/sync_alpaca_state.py`:
```python
if not api_key or not api_secret:
    logger.warning("⚠️ No Alpaca API keys found - using simulated mode")
    return {
        "equity": 100000.0,  # FAKE DATA
        "mode": "simulated",
    }
```

The "simulated mode" fallback was a **silent lie** - it pretended to succeed while writing garbage.

## Fix Applied

1. Added `AlpacaSyncError` exception class
2. Missing API keys now RAISES exception instead of returning fake data
3. Added validation in `update_system_state()` to REJECT simulated data
4. Script now returns exit code 1 (failure) when it can't get real data

## Prevention

1. **Never silently fallback to fake data** - fail loudly instead
2. **Validate data mode before writing** - reject "simulated" overwrites
3. **Exit codes must reflect reality** - 0 = real success only
4. **Test the failure path** - verify the hook blocks on sync failure

## Anti-Pattern

```python
# WRONG - Silent fallback
if error:
    return default_fake_data()  # Lies!

# RIGHT - Loud failure
if error:
    raise RealError("Cannot proceed - fix the underlying issue")
```

## Tags

`data-integrity`, `anti-lying`, `critical`, `sync`, `alpaca`

