# LL-158: Lesson LL-158: Day 74 Emergency Fix - SPY to SOFI

**Date**: 2026-01-13
**Severity**: CRITICAL
**Category**: Trading Strategy

## Problem
Day 74/90 with $0 profit in paper account. System was blocking all trades.

## Root Causes
1. **Wrong target asset**: guaranteed_trader.py targeted SPY ($580/share) instead of SOFI (~$15/share)
2. **Overly complex gates**: RSI checks and RAG queries blocked nearly all trades
3. **Misaligned watchlist**: Listed NVDA/GOOGL which require $10K+ for CSPs
4. **Cash threshold too high**: Required $5000 cash before trading (line 300)

## Fix Applied
1. Changed guaranteed_trader.py from SPY to SOFI
2. Removed RSI gate (was blocking unless RSI < 30 or > 70)
3. Removed RAG gate (was querying for "failures" and blocking)
4. Updated watchlist to F/SOFI/BAC (matches CLAUDE.md strategy)
5. Simplified logic: Buy $100 SOFI daily, no conditions

## Evidence
- PR #1537 merged via GitHub API
- Commit: d3102c2a4e83891807a920d1d9b36d4329e5975a
- Files changed: data/tier2_watchlist.json, scripts/guaranteed_trader.py

## Prevention
1. Always verify trading targets match CLAUDE.md strategy
2. Test with real symbols before deployment
3. Remove gates that have no empirical evidence of value
4. Check paper account daily for actual position changes

## Lesson
Complexity is the enemy of execution. 74 days of zero profit because the system was too "smart" to make simple trades.
