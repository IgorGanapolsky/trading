# Lesson Learned #119: Paper Trading API Key Mismatch After Account Reset

**Date**: January 8, 2026
**Severity**: HIGH
**Category**: Configuration/Infrastructure

## Summary
Paper trading was completely broken because one workflow job still referenced OLD API secrets (`ALPACA_PAPER_TRADING_API_KEY`) after the paper account was reset to new $5K account with different credentials (`ALPACA_PAPER_TRADING_5K_API_KEY`).

## What Happened
1. On Jan 7, 2026, CEO reset paper account to $5,000 with NEW API credentials
2. Most workflow jobs were updated to use `ALPACA_PAPER_TRADING_5K_API_KEY`
3. The `protect-existing-positions` job in `daily-trading.yml` still used OLD secrets
4. This caused a credential mismatch that could block pre-market protection
5. No trades executed on Jan 7 or Jan 8 (2 days of paper trading lost)

## Root Cause
Inconsistent secret naming across workflow jobs. When the paper account was reset, not all jobs were updated to use the new `_5K` suffixed secrets.

**Location of bug**: `.github/workflows/daily-trading.yml` lines 286-287

```yaml
# BEFORE (broken):
ALPACA_API_KEY: ${{ secrets.ALPACA_PAPER_TRADING_API_KEY }}
ALPACA_SECRET_KEY: ${{ secrets.ALPACA_PAPER_TRADING_API_SECRET }}

# AFTER (fixed):
ALPACA_API_KEY: ${{ secrets.ALPACA_PAPER_TRADING_5K_API_KEY }}
ALPACA_SECRET_KEY: ${{ secrets.ALPACA_PAPER_TRADING_5K_API_SECRET }}
```

## Impact
- 2 days of paper trading missed (Jan 7-8, 2026)
- No Phil Town strategy validation during this period
- Potential stop-loss protection gaps for existing positions

## Fix Applied
Updated `protect-existing-positions` job to use correct `_5K` suffixed secrets.

## Prevention
1. **ALWAYS** grep for ALL secret references when changing secret names
2. Create a centralized environment file or reusable workflow for secrets
3. Add CI check to validate all secret references match expected pattern
4. When resetting accounts, create a checklist of ALL places that reference API keys

## Verification Commands
```bash
# Check for old secret references (should return 0 results after fix)
grep -r "ALPACA_PAPER_TRADING_API_KEY[^_]" .github/workflows/
grep -r "ALPACA_PAPER_TRADING_API_SECRET[^_]" .github/workflows/

# Check for new secret references (should find multiple)
grep -r "ALPACA_PAPER_TRADING_5K" .github/workflows/
```

## Related Lessons
- ll_117: ChromaDB Removal Caused 2-Day Trading Gap
- ll_111: Paper Capital Must Match Real (Jan 7, 2026)
