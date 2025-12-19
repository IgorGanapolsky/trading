# Lesson Learned #052: We Do NOT Trade Crypto - Remove All References

**Date**: December 19, 2025
**Severity**: MEDIUM
**Category**: System Configuration

## The Problem

The trading context hook displayed:
```
Markets: Equities: OPEN | Crypto: OPEN 24/7
```

This is WRONG because:
1. We do NOT trade cryptocurrency
2. Our system is US equities and options ONLY
3. Mentioning crypto confuses the AI and user about what we trade

## Root Cause

Old code from initial setup when crypto was considered. The hook was never updated when the decision was made to focus on US equities only.

## The Fix

Removed all crypto references from the hook:

Before:
```bash
CRYPTO_STATUS="OPEN 24/7"
MARKET_STATUS="Equities: $EQUITY_STATUS | Crypto: $CRYPTO_STATUS"
```

After:
```bash
# Check market status - US Equities ONLY (we don't trade crypto)
MARKET_STATUS="OPEN (Mon-Fri 9:30-4:00 ET)"
```

## Prevention

- Audit codebase for outdated asset class references
- Keep CLAUDE.md and hooks aligned with actual trading strategy
- When strategy changes, update ALL related files

## What We Trade

| Asset Class | Status |
|-------------|--------|
| US Equities (SPY, etc.) | YES |
| US Options | YES |
| Crypto | NO |
| Forex | NO |
| Futures | NO |

## Tags

#configuration #crypto #strategy #cleanup
